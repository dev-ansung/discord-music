import os
import sys
import datetime
import argparse
from typing import BinaryIO
from loguru import logger as log
from faster_whisper import WhisperModel
import numpy as np


# Google-style Docstrings as requested
class WhisperTranscriber:
    """Handles real-time transcription of a raw PCM stream using Whisper."""

    def __init__(self, model_size: str = "base"):
        """Initializes the Whisper model.

        Args:
            model_size: Size of the model (tiny, base, small, medium, large-v3).
        """
        log.debug(f"Loading Whisper model: {model_size}")
        # Using CPU for accessibility, change to 'cuda' if GPU is available
        self.model = WhisperModel(model_size, device="cpu", compute_type="int8")

    def transcribe_stream(self, pipe_path: str, output_path: str):
        """Reads PCM data from a pipe and transcribes it in chunks."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        log.info(f"👂 Listening to {pipe_path}...")

        # Buffer: ~4 seconds of 48kHz Stereo 16-bit audio
        # Calculation: 4s * 48000Hz * 2 channels * 2 bytes = 768000 bytes
        chunk_size = 768000

        try:
            # We open the pipe in binary mode
            with (
                open(pipe_path, "rb") as pcm_in,
                open(output_path, "a", encoding="utf-8") as text_out,
            ):
                while True:
                    raw_bytes = pcm_in.read(chunk_size)
                    if not raw_bytes:
                        continue

                    # 1. Convert raw bytes to NumPy array (s16le)
                    audio_array = (
                        np.frombuffer(raw_bytes, dtype=np.int16)
                        .flatten()
                        .astype(np.float32)
                        / 32768.0
                    )

                    # 2. Reshape to Stereo and Downmix to Mono
                    audio_stereo = audio_array.reshape(-1, 2)
                    audio_mono = audio_stereo.mean(axis=1)

                    # 3. Resample from 48kHz to 16kHz (Simple slicing for performance)
                    # Slicing every 3rd sample: 48000 / 3 = 16000
                    audio_16k = audio_mono[::3]

                    # 4. Transcribe the processed NumPy array
                    segments, _ = self.model.transcribe(audio_16k, beam_size=5)

                    for segment in segments:
                        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                        entry = f"[{timestamp}] {segment.text}\n"
                        text_out.write(entry)
                        text_out.flush()
                        sys.stdout.write(entry)
                        sys.stdout.flush()

        except KeyboardInterrupt:
            log.info("Transcription stopped.")
        except Exception as e:
            log.error(f"Transcription error: {e}")


def main():
    # Format the datetime in the output path as requested
    now_str = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    default_output = f"./artifacts/transcript-{now_str}.txt"

    parser = argparse.ArgumentParser(
        description="Real-time Discord Whisper Transcriber"
    )
    parser.add_argument("pipe", help="Path to /tmp/discord_listener_output.pcm")
    parser.add_argument(
        "output", nargs="?", default=default_output, help="Path to output text file"
    )
    args = parser.parse_args()

    # Handle the {datetime} placeholder if provided in string
    output_path = args.output.replace("{datetime}", now_str)

    transcriber = WhisperTranscriber(model_size="base")
    transcriber.transcribe_stream(args.pipe, output_path)


if __name__ == "__main__":
    main()
