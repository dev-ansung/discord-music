import os
import logging
from discord.ext import voice_recv

log = logging.getLogger(__name__)


class LazyPipeSink(voice_recv.AudioSink):
    """Writes captured audio to a pipe. Connects only when the pipe has a reader."""

    def __init__(self, pipe_path: str):
        self.pipe_path = pipe_path
        self.fd = None

    def wants_opus(self) -> bool:
        return False  # We want decoded PCM

    def write(self, user, data):
        # 1. Lazy Connection
        if self.fd is None:
            try:
                # O_NONBLOCK prevents hanging if no reader is attached
                self.fd = os.open(self.pipe_path, os.O_WRONLY | os.O_NONBLOCK)
                log.info(f"✅ Listener Pipe Connected: {self.pipe_path}")
            except OSError as e:
                # Errno 6 = Device not configured (No reader yet). Drop packet.
                if e.errno != 6:
                    log.warning(f"Pipe open failed: {e}")
                return

        # 2. Write Data
        if data and data.pcm:
            try:
                os.write(self.fd, data.pcm)
            except (BrokenPipeError, BlockingIOError):
                # Reader disconnected or full. Reset.
                self._close_fd()

    def cleanup(self):
        self._close_fd()

    def _close_fd(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None
