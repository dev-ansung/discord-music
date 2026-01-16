import argparse
import shlex

import pydantic


class VlcConfig(pydantic.BaseModel):
    """Type definition for VLC configuration options."""

    source: str
    pipe: str
    mute_local: bool
    volume: float
    latency: int
    headless: bool
    verbose: bool


def build_vlc_command(config: VlcConfig) -> str:
    """Constructs the shell command to launch VLC based on config parameters.

    This function handles the 'sout' chain logic, including muxing to raw PCM,
    optional gain filtering, and audio routing (duplicate vs single stream).
    """
    vlc_bin = "/Applications/VLC.app/Contents/MacOS/VLC"

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
        vlc_bin,
        "-I dummy" if config.headless else "",
        shlex.quote(config.source) if config.source else "",
        f"--file-caching={config.latency}",
        f"--network-caching={config.latency}",
        f"--verbose={1 if config.verbose else 0}",
        f"--sout={sout}",
    ]

    return " ".join(filter(None, cmd))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate VLC command for Discord streaming."
    )
    parser.add_argument("--source", type=str, default="", help="Input media source.")
    parser.add_argument(
        "--pipe",
        type=str,
        default="/tmp/discord_speaker_input.pcm",
        help="Output pipe path.",
    )
    parser.add_argument(
        "--mute_local", action="store_true", help="Mute local Mac speakers."
    )
    parser.add_argument("--volume", type=float, default=1.0, help="Volume gain.")
    parser.add_argument(
        "--latency", type=int, default=300, help="Caching in milliseconds."
    )
    parser.add_argument("--headless", action="store_true", help="Run without GUI.")
    parser.add_argument(
        "--verbose", action="store_true", help="Enable VLC verbose logs."
    )
    args = parser.parse_args()
    config = VlcConfig(**vars(args))

    print("\n--- Generated VLC Command ---")
    print(build_vlc_command(config))
