from discord_bridge import AudioBridge


import threading
import time
from typing import Optional


def start_intercom(
    token: str, channel_id: int, music_source_path: Optional[str] = None
):
    """Starts a bidirectional audio bridge for simultaneous music and recording."""
    bridge = AudioBridge(token)
    bridge.connect(channel_id)

    def recording_worker():
        """Thread responsibility: Read from Discord and save to disk."""
        print(
            "👂 Listener Thread: Active. Recording to '/tmp/discord_listener_output.pcm'..."
        )
        try:
            # Open the listener pipe and a destination file
            # Note: bridge.listener provides the read-stream
            with (
                bridge.listener as pcm_in,
                open("/tmp/discord_listener_output.pcm", "wb") as f,
            ):
                while True:
                    data = pcm_in.read(4096)
                    if data:
                        f.write(data)
                        # Optional: pcm_in.flush() isn't needed for reads,
                        # but we ensure file is written.
        except Exception as e:
            print(f"Listener Thread Error: {e}")

    def music_worker():
        """Thread responsibility: Read music from a file and push to Discord."""
        if not music_source_path:
            print(
                "ℹ️ No music source provided. Speaker will send silence (Heartbeat only)."
            )
            return

        print(f"🎵 Speaker Thread: Active. Streaming {music_source_path}...")
        try:
            # In a real app, you'd use FFmpeg here. For this logic,
            # we simulate manual streaming from a pre-recorded PCM file.
            with open(music_source_path, "rb") as music_in:
                speaker_out = bridge.speaker
                while True:
                    chunk = music_in.read(4096)
                    if not chunk:
                        # Loop music or break
                        break
                    speaker_out.write(chunk)
                    speaker_out.flush()
                    # Sleep to match 48kHz stereo timing (~21ms per 4096 bytes)
                    time.sleep(0.02)
        except Exception as e:
            print(f"Speaker Thread Error: {e}")

    # Initialize Threads
    listener_thread = threading.Thread(target=recording_worker, daemon=True)
    speaker_thread = threading.Thread(target=music_worker, daemon=True)

    # Start Concurrency
    listener_thread.start()
    speaker_thread.start()

    print("\n🚀 INTERCOM ONLINE")
    print("Streaming music AND recording chat simultaneously.")
    print("Press Ctrl+C to terminate.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down bridge...")
        bridge.close()


if __name__ == "__main__":
    import os

    start_intercom(os.getenv("DISCORD_BOT_TOKEN"), 834658744729075726)
