import os
import logging
from typing import BinaryIO

log = logging.getLogger(__name__)


class PipeManager:
    """Manages the lifecycle of filesystem FIFOs (Named Pipes)."""

    def __init__(self, speaker_pipe: str, listener_pipe: str):
        self.speaker_path = speaker_pipe
        self.listener_path = listener_pipe

    def create_pipes(self):
        """Ensures pipes exist and are clean."""
        for path in [self.speaker_path, self.listener_path]:
            if os.path.exists(path):
                os.remove(path)
            os.mkfifo(path)
            log.debug(f"FIFO created: {path}")

    def get_speaker_writer(self) -> BinaryIO:
        """Returns a writable file object for the Speaker input."""
        # Open in binary write mode
        return open(self.speaker_path, "wb")

    def get_listener_reader(self) -> BinaryIO:
        """Returns a readable file object for the Listener output."""
        # Open in binary read mode
        return open(self.listener_path, "rb")
