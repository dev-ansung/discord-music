import os
import discord
import asyncio
from discord.ext import commands, voice_recv
from loguru import logger as log
from discord.ext.voice_recv.opus import PacketDecoder

_original_decode_packet = PacketDecoder._decode_packet


def safe_decode_packet(self, packet):
    """A wrapper that catches OpusErrors to prevent thread crashes."""
    try:
        # Try to decode normally
        return _original_decode_packet(self, packet)
    except Exception as e:
        # If it fails (Corrupted Stream), log it and return empty PCM
        # This effectively 'skips' the bad packet instead of crashing
        log.warning(f"⚠️ Dropped corrupted packet: {e}")
        return packet, b""


PacketDecoder._decode_packet = safe_decode_packet
log.info("🩹 Applied fault-tolerance patch to PacketDecoder")

# --- CONFIGURATION ---
PIPE_PATH = "/tmp/discord_speaker_input.pcm"
# Check env vars immediately to fail fast if missing
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not DISCORD_TOKEN:
    log.error("DISCORD_BOT_TOKEN environment variable not set!")
    exit(1)

# Ensure Opus is loaded (Critical for Voice)
try:
    # Adjust path if needed for your specific Mac setup (Homebrew M1/M2 usually here)
    discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
except Exception as e:
    log.warning(f"Could not load custom libopus: {e}. Falling back to system default.")


class JukeboxBot(commands.Bot):
    """A minimal Discord bot designed to stream to/from local pipes."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def on_ready(self):
        log.info(f"✅ Jukebox Bot authenticated as {self.user}")
        log.info(f"   Discord.py Version: {discord.__version__}")

    async def on_command_error(self, ctx, error):
        """Global error handler to catch and log command failures."""
        if isinstance(error, commands.CommandNotFound):
            return
        log.error(f"❌ Command Error in '{ctx.command}': {error}")
        await ctx.send(f"⚠️ An error occurred: {str(error)}")


bot = JukeboxBot()


# --- AUDIO SINK (LISTENER) ---
class PCMStoreSink(voice_recv.AudioSink):
    """Writes incoming voice data to a local file with robust error handling."""

    def __init__(self, filename):
        self.filename = filename
        self.file = None
        self.bytes_written = 0
        try:
            self.file = open(filename, "wb")
            log.info(f"🎙️  Sink initialized. Writing raw PCM to {self.filename}")
        except Exception as e:
            log.error(f"Failed to open sink file: {e}")
            raise e

    def wants_opus(self) -> bool:
        """We want decoded PCM, not raw Opus packets."""
        return False

    def write(self, user, data):
        """Callback from the library when audio data is received."""
        try:
            if data and data.pcm:
                self.file.write(data.pcm)
                self.bytes_written += len(data.pcm)

                # Log progress every ~1MB (1,000,000 bytes)
                if self.bytes_written % 1_000_000 < 4000:
                    log.debug(
                        f"📥 Captured {self.bytes_written / 1024 / 1024:.2f} MB of audio..."
                    )
        except Exception as e:
            log.error(f"Error writing PCM data: {e}")

    def cleanup(self):
        if self.file and not self.file.closed:
            try:
                self.file.flush()
                self.file.close()
                log.info(
                    f"✅ Sink closed. Total captured: {self.bytes_written / 1024 / 1024:.2f} MB"
                )
            except Exception as e:
                log.error(f"Error closing sink file: {e}")


# --- COMMANDS ---


@bot.command()
async def join(ctx: commands.Context):
    """Joins voice and opens the FIFO pipe as a standard file source."""
    if not ctx.author.voice:
        return await ctx.send("User not in a voice channel.")

    channel = ctx.author.voice.channel

    try:
        vc = await channel.connect()
    except discord.ClientException:
        await ctx.send("I'm already connected to a voice channel.")
        return

    log.info(f"🔗 Connected to {channel}. Opening pipe: {PIPE_PATH}")

    if not os.path.exists(PIPE_PATH):
        await ctx.send(f"⚠️ Pipe not found at {PIPE_PATH}. Is the producer running?")
        return

    try:
        # We use a standard file reader, but FFmpeg handles the FIFO blocking
        source = discord.FFmpegPCMAudio(
            PIPE_PATH, before_options="-f s16le -ar 48000 -ac 2"
        )
        vc.play(source, after=lambda e: log.info(f"Playback stopped: {e}"))
        await ctx.send(f"🔊 Playing from pipe...")
    except Exception as e:
        log.error(f"Failed to start playback: {e}")
        await ctx.send("Failed to start playback.")


@bot.command()
async def leave(ctx: commands.Context):
    """Disconnects from voice and cleans up."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        log.info("👋 Bot disconnected from voice channel.")
        await ctx.send("Disconnected.")
    else:
        await ctx.send("I am not in a voice channel.")


@bot.command()
async def listen(ctx):
    """Starts recording the voice channel to a file."""
    if not ctx.author.voice:
        return await ctx.send("You must be in a voice channel.")

    # 1. Connect using the VoiceRecvClient
    try:
        vc = await ctx.author.voice.channel.connect(cls=voice_recv.VoiceRecvClient)
    except Exception as e:
        log.error(f"Connection failed: {e}")
        return await ctx.send("Could not connect to voice.")

    # 2. STABILIZATION: Play silence to establish RTP flow
    # This sends 5 seconds of silent audio. It forces Discord to acknowledge
    # the bot as a valid endpoint, reducing "Corrupted Stream" errors.
    log.debug("🛡️ Starting infinite silence heartbeat...")
    silence_source = discord.FFmpegPCMAudio(
        "/dev/zero", before_options="-f s16le -ar 48000 -ac 2"
    )
    vc.play(silence_source)

    # Wait a moment for the handshake to settle
    await asyncio.sleep(1)

    # 3. Start Listening
    capture_file = "/tmp/discord_listener_output.pcm"
    vc.listen(PCMStoreSink(capture_file))

    log.info(f"🔴 Listening started. Recording to {capture_file}")
    await ctx.send("I am now listening to this channel.")


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        log.info("Shutting down bot...")
    except Exception as e:
        log.critical(f"Fatal startup error: {e}")
