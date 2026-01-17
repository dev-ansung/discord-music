import argparse
import logging
import os

import discord
from discord.ext import commands, voice_recv

log = logging.getLogger(__name__)


class DiscordRecorder:
    """Discord bot that records audio from a voice channel to a file."""

    def __init__(self, token: str, channel_id: int, output_path: str):
        self.token = token
        self.channel_id = channel_id
        self.output_path = output_path
        self.bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())
        # load Opus library
        discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")

        @self.bot.event
        async def on_ready():
            log.info(f"Bot Connected: {self.bot.user}")
            await self.connect_and_record()

    async def connect_and_record(self):
        channel = self.bot.get_channel(self.channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            log.error(f"Channel ID {self.channel_id} is not a voice channel.")
            return

        voice_client = await channel.connect(cls=voice_recv.VoiceRecvClient)
        log.info(f"Connected to Voice Channel: {channel.name} ({channel.id})")
        voice_client.listen(voice_recv.BasicSink(self.save_audio))
        log.info(f"Recording audio to: {self.output_path}")

    def save_audio(self, user, data):
        if not user:
            return
        with open(self.output_path, "ab") as f:
            log.info(f"Writing audio data for user {user.name}")
            f.write(data.pcm)

    def start(self):
        self.bot.run(self.token)


if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError("DISCORD_BOT_TOKEN environment variable is required.")
    # Example usage of DiscordRecorder
    parser = argparse.ArgumentParser(description="Discord Audio Recorder")
    parser.add_argument(
        "--channel-id",
        type=int,
        default=834658744729075726,
        help="Discord Voice Channel ID to connect to.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./artifacts/test_output.pcm",
        help="Path to save recorded audio from Discord.",
    )
    args = parser.parse_args()
    recorder = DiscordRecorder(token, args.channel_id, args.output)
    recorder.start()
