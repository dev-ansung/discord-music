import argparse
import asyncio
import logging
import os

import discord
from discord.ext import commands

log = logging.getLogger(__name__)


class DiscordSpeaker:
    """Discord bot that connects to a channel and plays an audio file.

    Attributes:
        token (str): The Discord bot token.
        channel_id (int): The ID of the voice channel to join.
        input_path (str): The path to the audio file to be played.
        bot (commands.Bot): The Discord bot instance.
    """

    def __init__(self, token: str, channel_id: int, input_path: str):
        """Initializes the DiscordSpeaker with token, channel, and input file.

        Args:
            token (str): The Discord bot token.
            channel_id (int): The target voice channel ID.
            input_path (str): Path to the input audio file (e.g., raw PCM).
        """
        self.token = token
        self.channel_id = channel_id
        self.input_path = input_path
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

        # TODO: Make the opus library path dynamic or configurable via env vars.
        try:
            discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
        except OSError:
            log.warning("Could not load Opus from default Homebrew path.")

        @self.bot.event
        async def on_ready():
            log.info(f"Bot Connected: {self.bot.user}")
            await self.connect_and_play()

    async def connect_and_play(self):
        """Connects to the voice channel and initiates audio playback."""
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            log.error(f"Channel ID {self.channel_id} is not a valid voice channel.")
            await self.bot.close()
            return

        try:
            voice_client = await channel.connect()
            log.info(f"Connected to Voice Channel: {channel.name} ({channel.id})")
            await self._play_file(voice_client)
        except Exception as e:
            log.exception(f"An error occurred during connection or playback.: {e}")
        finally:
            if self.bot:
                await self.bot.close()

    async def _play_file(self, voice_client: discord.VoiceClient):
        """Plays the audio file to the connected voice client.

        Args:
            voice_client (discord.VoiceClient): The connected voice client instance.
        """
        if not os.path.exists(self.input_path):
            log.error(f"Input file not found: {self.input_path}")
            return

        log.info(f"Preparing to play: {self.input_path}")

        audio_setting = None
        if self.input_path.endswith(".mp3"):
            audio_setting = "-f mp3"
        elif self.input_path.endswith(".wav"):
            audio_setting = "-f wav"
        elif self.input_path.endswith(".pcm"):
            audio_setting = "-f s16le -ar 48000 -ac 2"
        else:
            log.warning("Unknown file extension. Defaulting to raw PCM settings.")
            audio_setting = "-f s16le -ar 48000 -ac 2"
        source = discord.FFmpegPCMAudio(self.input_path, options=audio_setting)

        voice_client.play(source)

        log.debug("Playback started. Waiting for audio to finish.")
        while voice_client.is_playing():
            await asyncio.sleep(1)

        log.info("Playback finished.")
        await voice_client.disconnect()

    def start(self):
        """Starts the bot client."""
        self.bot.run(self.token)


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required.")

    parser = argparse.ArgumentParser(description="Discord Audio Speaker")
    parser.add_argument(
        "--channel-id",
        type=int,
        default=834658744729075726,
        help="Discord Voice Channel ID to connect to.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="./artifacts/test_output.pcm",
        help="Path to the audio file to play.",
    )
    args = parser.parse_args()

    speaker = DiscordSpeaker(token, args.channel_id, args.input)
    speaker.start()
