# Discord Intercom

A high-performance Discord voice utility designed for Senior Engineers who need low-latency audio recording and playback. This project leverages `discord-ext-voice-recv` for full-duplex audio and uses **Named Pipes (FIFOs)** to bridge external media players like VLC with the Discord Voice Gateway.

![GitHub License](https://img.shields.io/github/license/user/repo)
![GitHub repo size](https://img.shields.io/github/repo-size/user/repo)
![Activity](https://img.shields.io/github/commit-activity/m/user/repo)


![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)
![Managed by uv](https://img.shields.io/badge/managed%20by-uv-purple)
![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)

![FFmpeg](https://img.shields.io/badge/dependency-ffmpeg-orange)
![discord.py](https://img.shields.io/badge/discord.py-v2.3.2-blue?logo=discord&logoColor=white)
![voice-recv](https://img.shields.io/badge/ext-voice--recv-blueviolet)

## Core Features

* **Real-time MP3 Encoding:** Records raw PCM from Discord and pipes it through FFmpeg to produce 192kbps MP3s on the fly.
* **VLC Integration:** Use VLC as a high-level GUI/Media engine to stream any source (YouTube, local files, network streams) into a Discord Voice Channel.
* **Full Duplex:** Capability to record and play audio simultaneously within the same bot session.

## Requirements

### System Dependencies

* **FFmpeg:** Required for audio transcoding and MP3 encoding.
* **libopus:** Required for Discord voice encryption.
* *macOS:* `brew install opus ffmpeg`


* **uv:** Recommended Python package and project manager.
* **VLC:** (Optional) Required for `discord_vlc.py` streaming.

### Environment Setup

Create a `.env` file in the root directory:

```bash
DISCORD_BOT_TOKEN=your_token_here
```

## Installation

```bash
uv sync
```

## Usage

### 1. Recording to MP3

Capture all audio from a specific voice channel.

```bash
source .env && uv run src/discord_intercom.py --channel-id {ID} --output recording.mp3
```

### 2. Basic Audio Playback

Stream a local raw PCM or MP3 file directly.

```bash
source .env && uv run src/discord_intercom.py --channel-id {ID} --input music.mp3

```

### 3. VLC-to-Discord Stream (GUI or Headless)

This command launches a VLC instance that pipes audio into the Discord bot. This allows you to use VLC's playlist and volume controls.

```bash
source .env && uv run src/discord_vlc.py --source "https://www.youtube.com/watch?v=..." --channel-id {ID}

```

---

## Technical Architecture: Audio Piping

The system uses a **Named Pipe (FIFO)** to transfer audio between VLC and the Bot. This prevents disk I/O bottlenecks and minimizes latency.

| Stage | Process | Format |
| --- | --- | --- |
| **Input** | VLC / FFmpeg | Source (MP3, URL, etc) |
| **Bridge** | Named Pipe (`.pcm`) | Raw PCM (s16le, 48kHz, Stereo) |
| **Output** | Discord Bot | Opus-encoded RTP Stream |

### Manual Pipe Debugging

If you need to verify the audio stream integrity outside of the bot:

**Generate PCM with FFmpeg:**

```bash
ffmpeg -i in.mp3 -f s16le -ar 48000 -ac 2 out.pcm

```

**Monitor Pipe with ffplay:**

```bash
ffplay -f s16le -ar 48000 -ch_layout stereo out.pcm

```

## Implementation Notes

* **Opus Path:** The project defaults to the Homebrew path for `libopus.dylib` on Apple Silicon. Adjust `SimpleRecorderSpeaker` initialization if using Linux or Intel Mac.
* **FFmpeg Buffering:** The recorder uses `stdin.flush()` to ensure real-time writing to the MP3 encoder, preventing data loss on process termination.

---

### Next Step

Would you like me to add a **Troubleshooting** section covering common `libopus` load errors or FFmpeg path issues on different operating systems?