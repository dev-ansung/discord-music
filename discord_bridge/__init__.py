import logging
import asyncio
from typing import BinaryIO
from .infrastructure import PipeManager
from .core import BridgeBot

# Configure Logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s"
)


class AudioBridge:
    """The High-Level Public Interface."""

    def __init__(self, token: str):
        # Define Paths
        self.pipes = PipeManager(
            speaker_pipe="/tmp/discord_speaker_input.pcm",
            listener_pipe="/tmp/discord_listener_output.pcm",
        )
        self.pipes.create_pipes()

        # Initialize Bot (Singleton)
        self.bot = BridgeBot(token, self.pipes)

        # Block until authenticated
        print("Waiting for Discord Auth...")
        self.bot._ready_event.wait()
        print("✅ Authenticated.")

    def connect(self, channel_id: int):
        """Connects the bridge to a specific voice channel."""
        future = asyncio.run_coroutine_threadsafe(
            self.bot.connect_and_bridge(channel_id), self.bot.loop
        )
        future.result()  # Wait for connection to finish

    @property
    def speaker(self) -> BinaryIO:
        """Get the stream to WRITE audio to."""
        return self.pipes.get_speaker_writer()

    @property
    def listener(self) -> BinaryIO:
        """Get the stream to READ audio from."""
        return self.pipes.get_listener_reader()

    def close(self):
        """Gracefully shuts down the bridge and cleans up resources."""
        if self.bot and self.bot.loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self.bot.disconnect_bridge(), self.bot.loop
            )
            try:
                future.result(timeout=5)  # Wait up to 5s for cleanup
            except Exception as e:
                print(f"Cleanup warning: {e}")
