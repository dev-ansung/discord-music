import argparse
import logging
import os
import signal
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import discord_intercom

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s:%(lineno)d - %(message)s",
)
log = logging.getLogger(__name__)


@dataclass
class VlcConfig:
    source: str
    pipe: str
    mute_local: bool
    volume: float
    latency: int
    headless: bool
    verbose: bool


class DiscordVlcStreamer:
    """Orchestrates VLC streaming into a Discord Bot via a named pipe."""

    def __init__(
        self, token: str, channel_id: int, vlc_config: VlcConfig, vlc_bin: str
    ):
        self.token = token
        self.channel_id = channel_id
        self.vlc_config = vlc_config
        self.vlc_process = None
        self.bot = None
        self.vlc_bin = vlc_bin

    def build_vlc_command(self, config: VlcConfig) -> str:
        """Constructs the shell command to launch VLC based on config parameters.

        This function handles the 'sout' chain logic, including muxing to raw PCM,
        optional gain filtering, and audio routing (duplicate vs single stream).
        """

        # Define the transcode segment: PCM s16l, 48kHz, Stereo
        gain = f",afilter=gain{{gain={config.volume}}}" if config.volume != 1.0 else ""
        transcode = (
            f"transcode{{acodec=s16l,channels=2,samplerate=48000{gain}}}:"
            f"std{{access=file,mux=raw,dst={config.pipe}}}"
        )

        # Routing: Duplicate to speakers unless mute_local is toggled
        sout = (
            f"'#duplicate{{dst=display,dst=\"{transcode}\"}}'"
            if not config.mute_local
            else f"'#{transcode}'"
        )
        # Assemble command arguments
        cmd = [
            self.vlc_bin,
            "-I dummy" if config.headless else "",
            f"{config.source}" if config.source else "",
            f"--file-caching={config.latency}",
            f"--network-caching={config.latency}",
            f"--verbose={1 if config.verbose else 0}",
            f"--sout={sout}",
        ]
        return " ".join(filter(None, cmd))

    def setup_fifo(self):
        """Creates a named pipe (FIFO) if it doesn't exist.

        We use a FIFO because it allows VLC to write audio and the Bot to read it
        simultaneously without creating massive temporary files on disk.
        """
        fifo_path = Path(self.vlc_config.pipe)

        # Clean up existing file
        if fifo_path.exists():
            fifo_path.unlink()

        try:
            os.mkfifo(fifo_path)
            log.info(f"Created named pipe at {fifo_path}")
        except OSError as e:
            log.error(f"Failed to create FIFO: {e}")
            sys.exit(1)

    def launch_vlc(self):
        """Generates the command and launches VLC as a subprocess."""
        cmd_str = self.build_vlc_command(self.vlc_config)
        log.info("Launching VLC...")
        log.debug(f"VLC Command: {cmd_str}")

        self.vlc_process = subprocess.Popen(
            cmd_str,
            shell=True,
            preexec_fn=os.setsid,
            stdout=subprocess.DEVNULL if not self.vlc_config.verbose else None,
            stderr=subprocess.DEVNULL if not self.vlc_config.verbose else None,
        )

    def run(self):
        """Main method to run the VLC to Discord streaming."""
        try:
            self.setup_fifo()
            self.launch_vlc()
            log.info("Starting Discord Bot...")
            self.bot = discord_intercom.DiscordIntercom(
                token=self.token,
                channel_id=self.channel_id,
                input_path=self.vlc_config.pipe,
            )
            self.bot.start()

        except KeyboardInterrupt:
            log.info("Interrupted by user. Shutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up processes and resources."""
        if self.vlc_process:
            log.info("Terminating VLC process...")
            try:
                os.killpg(os.getpgid(self.vlc_process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
            except Exception as e:
                log.error(f"Error killing VLC: {e}")
        if os.path.exists(self.vlc_config.pipe):
            os.unlink(self.vlc_config.pipe)


def main(VlcConfig, DiscordVlcStreamer):
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: DISCORD_BOT_TOKEN environment variable is required.")
        sys.exit(1)
    parser = argparse.ArgumentParser(description="Discord VLC Streamer")
    parser.add_argument(
        "--channel-id", type=int, required=True, help="Discord Voice Channel ID."
    )
    parser.add_argument(
        "--source", type=str, required=True, help="Input media source (URL or File)."
    )
    parser.add_argument(
        "--pipe",
        type=str,
        default="/tmp/discord_vlc.pcm",
        help="Path for the named pipe.",
    )
    parser.add_argument(
        "--mute-local", action="store_true", help="Mute local playback."
    )
    parser.add_argument("--volume", type=float, default=1.0, help="Volume multiplier.")
    parser.add_argument(
        "--latency", type=int, default=500, help="Caching/Latency in ms."
    )
    parser.add_argument("--verbose", action="store_true", help="Show VLC logs.")
    parser.add_argument("--headless", action="store_true", help="Run VLC without GUI.")
    parser.add_argument(
        "--vlc-bin",
        type=str,
        default="/opt/homebrew/bin/vlc",
    )
    args = parser.parse_args()

    vlc_config = VlcConfig(
        source=args.source,
        pipe=args.pipe,
        mute_local=args.mute_local,
        volume=args.volume,
        latency=args.latency,
        headless=args.headless,
        verbose=args.verbose,
    )

    streamer = DiscordVlcStreamer(token, args.channel_id, vlc_config, args.vlc_bin)
    streamer.run()


if __name__ == "__main__":
    main(VlcConfig, DiscordVlcStreamer)
