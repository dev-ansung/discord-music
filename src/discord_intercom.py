import argparse
import asyncio
import logging
import os
import subprocess
from typing import Optional

import discord
from discord.ext import commands, voice_recv

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logging.getLogger("discord.ext.voice_recv.reader").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


class DiscordIntercom:
    def __init__(
        self,
        token: str,
        channel_id: int,
        input_path: Optional[str] = None,
        output_path: Optional[str] = None,
    ):
        self.token = token
        self.channel_id = channel_id
        self.input_path = input_path
        self.output_path = output_path
        self.encoder_process = None
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

        try:
            discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
        except OSError as err:
            raise RuntimeError(
                "Opus library not found. Make sure libopus is installed."
            ) from err

        @self.bot.event
        async def on_ready():
            log.info(f"Bot Connected: {self.bot.user}")
            await self.connect_and_operate()

    async def connect_and_operate(self):
        """Connects to the voice channel and starts recording/playing as configured."""
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            log.error(f"Channel ID {self.channel_id} is not a valid voice channel.")
            await self.bot.close()
            return

        try:
            voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
            log.info(f"Connected to Voice Channel: {channel.name} ({channel.id})")

            if self.input_path:
                self.bot.loop.create_task(self._play_audio(voice_client))
                log.info("Playback started...")

            if self.output_path:
                self._start_mp3_encoder()
                voice_client.listen(voice_recv.BasicSink(self.save_audio))
                log.info("Recording started...")

        except Exception:
            log.exception("An error occurred during voice operations.")
            await self.cleanup()

    def _start_mp3_encoder(self):
        """Starts an ffmpeg process to encode raw PCM to MP3 in real-time.

        Input: Raw PCM, Signed 16-bit Little Endian, 48000Hz, Stereo
        Output: MP3, 192k bitrate
        """
        log.info(f"Streaming recording to: {self.output_path}")
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-i",
            "pipe:0",
            "-acodec",
            "libmp3lame",
            "-b:a",
            "192k",
            self.output_path,
        ]

        # Open the process with a pipe for stdin
        self.encoder_process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL
        )

    def save_audio(self, user, data):
        """Pipes received PCM data directly to the ffmpeg encoder."""
        if not user:
            return
        if self.encoder_process and self.encoder_process.stdin:
            try:
                self.encoder_process.stdin.write(data.pcm)
            except BrokenPipeError:
                log.error("FFmpeg process died unexpectedly.")

    async def _play_audio(self, voice_client):
        """Plays audio from the specified input file."""
        if not self.input_path or not os.path.exists(self.input_path):
            log.error(f"Input file not found: {self.input_path}")
            return

        log.info(f"Playing: {self.input_path}")
        ffmpeg_options = None
        if self.input_path.lower().endswith(".mp3"):
            pass
        elif self.input_path.lower().endswith(".wav"):
            pass
        else:
            if not self.input_path.lower().endswith(".pcm"):
                log.warning("Unknown input format. Defaulting to raw PCM assumptions.")
            ffmpeg_options = "-f s16le -ar 48000 -ac 2"
        source = discord.FFmpegPCMAudio(
            self.input_path,
            before_options=ffmpeg_options,
        )
        voice_client.play(source)

        while voice_client.is_playing():
            await asyncio.sleep(1)

    async def cleanup(self):
        """Gracefully closes connections and encoding processes."""
        log.info("Cleaning up resources...")

        if self.encoder_process:
            if self.encoder_process.stdin:
                self.encoder_process.stdin.close()
            self.encoder_process.wait()
            log.info("MP3 encoding finished.")

        if self.bot:
            await self.bot.close()

    def start(self):
        try:
            self.bot.run(self.token)
        except KeyboardInterrupt:
            asyncio.run(self.cleanup())


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required.")

    parser = argparse.ArgumentParser(description="Discord MP3 Recorder & Speaker")
    parser.add_argument("--channel-id", type=int, required=True)
    parser.add_argument("--input", type=str, default=None)
    parser.add_argument("--output", type=str, default=None)

    args = parser.parse_args()

    bot = DiscordIntercom(
        token=token,
        channel_id=args.channel_id,
        input_path=args.input,
        output_path=args.output,
    )
    bot.start()
