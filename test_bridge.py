import os
import sys
import math
import time
import struct
import argparse
from discord_bridge import AudioBridge

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = 834658744729075726


def generate_sine_wave(duration_seconds=5, freq=440):
    """Generates a raw PCM sine wave (Beep) for testing audio output."""
    sample_rate = 48000
    amplitude = 16000  # ~50% volume
    total_samples = sample_rate * duration_seconds
    pcm_data = bytearray()

    print(f"Generating {duration_seconds}s sine wave at {freq}Hz...")
    for i in range(total_samples):
        # Calculate sine value
        t = i / sample_rate
        value = int(amplitude * math.sin(2 * math.pi * freq * t))

        # Pack as signed 16-bit little endian (s16le)
        # We write the same value to Left and Right channels (Stereo)
        packed = struct.pack("<hh", value, value)
        pcm_data.extend(packed)

    return pcm_data


def test_speaker(bridge):
    print("\n--- 📢 TEST 1: SPEAKER ---")
    print("Generating tone...")
    # Increase duration and volume for clarity
    beep_data = generate_sine_wave(duration_seconds=5, freq=440)

    writer = bridge.speaker
    print(f"Writing {len(beep_data)} bytes to Discord...")

    chunk_size = 4096
    # Write the audio
    for i in range(0, len(beep_data), chunk_size):
        chunk = beep_data[i : i + chunk_size]
        writer.write(chunk)
        writer.flush()
        # Simulate real-time speed
        time.sleep(chunk_size / (48000 * 4))

    print("✅ Data written. Waiting for network drain...")
    # Wait for audio to travel through the pipe/internet
    time.sleep(3)
    print("✅ Done!")


def test_listener(bridge):
    """Test 2: Read audio from the Listener pipe."""
    print("\n--- 👂 TEST 2: LISTENER ---")
    print("speak into your microphone now!")
    print("Recording 5 seconds...")

    reader = bridge.listener
    output_filename = "test_capture.pcm"

    # 5 seconds * 48000 Hz * 2 channels * 2 bytes = 960,000 bytes
    bytes_to_read = 960_000
    bytes_read = 0

    with open(output_filename, "wb") as f:
        while bytes_read < bytes_to_read:
            # This blocks until someone speaks!
            chunk = reader.read(4096)
            if not chunk:
                continue
            f.write(chunk)
            bytes_read += len(chunk)
            sys.stdout.write(
                f"\rCaptured: {bytes_read / 1024:.2f} KB / {bytes_to_read / 1024:.2f} KB"
            )
            sys.stdout.flush()

    print(f"\n✅ Done! Saved to {output_filename}")
    print(
        f"Play it with: ffplay -f s16le -ar 48000 -ch_layout stereo {output_filename}"
    )


def main():
    parser = argparse.ArgumentParser(description="Test suite for Discord Audio Bridge")
    parser.add_argument(
        "mode", choices=["speaker", "listener", "all"], help="Which component to test"
    )
    args = parser.parse_args()

    print("Initializing Bridge...")
    bridge = AudioBridge(TOKEN)
    bridge.connect(CHANNEL_ID)

    try:
        if args.mode in ["speaker", "all"]:
            test_speaker(bridge)

        if args.mode in ["listener", "all"]:
            test_listener(bridge)

    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    finally:
        # --- THE FIX ---
        print("\nCleaning up...")
        bridge.close()
        print("✅ Shutdown Complete.")


if __name__ == "__main__":
    main()
