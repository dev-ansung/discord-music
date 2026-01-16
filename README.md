# Discord Audio Bridge

**A high-performance, bidirectional audio interface for Discord Bots.**



This project implements a robust **Audio Bridge** that decouples your application logic from the Discord Gateway. It exposes standard POSIX pipes (FIFOs) for input and output, allowing you to stream high-quality audio from any local source (FFmpeg, VLC, MPV) directly into a voice channel, and record voice chat in real-time.

## 🚀 Key Features

* **Unix-Style Interface:** treat Discord audio like a file stream (`read`/`write`).
* **Fault Tolerant:** Implements a "Heartbeat" silence carrier to prevent Discord from dropping the connection during silence.
* **Bidirectional:** Separate, isolated pipes for Speaking and Listening to prevent collision.
* **Lazy Connection:** Pipes auto-heal and wait for readers/writers without crashing the bot.
* **System Native:** Zero-copy data movement using OS-level FIFOs.

---

## 🛠 Architecture

The system operates on a **Strict Separation** model using two unidirectional named pipes:

1.  **Speaker Pipe (`/tmp/discord_speaker_input.pcm`)**:
    * **Input:** Your App / VLC / FFmpeg (Writes PCM data).
    * **Process:** The Bot mixes this stream with infinite silence (Heartbeat).
    * **Output:** Discord Voice Channel.
2.  **Listener Pipe (`/tmp/discord_listener_output.pcm`)**:
    * **Input:** Discord Voice Channel (Opus packets).
    * **Process:** The Bot decodes packets to PCM.
    * **Output:** Your App (Reads PCM data).

---

## 📋 Prerequisites

* **OS:** macOS or Linux (Windows is not supported due to `os.mkfifo` reliance).
* **Python:** 3.10+ (Tested on 3.14).
* **System Libraries:**
    * **FFmpeg:** Required for audio mixing and transcoding.
    * **libopus:** Required for Discord voice encoding.

### macOS (Homebrew)
```bash
brew install ffmpeg opus

```

### Linux (Debian/Ubuntu)

```bash
sudo apt update && sudo apt install ffmpeg libopus-dev

```

---

## 📦 Installation

This project uses `uv` for modern dependency management, but standard `pip` works as well.

1. **Clone the repository:**
```bash
git clone [https://github.com/yourusername/discord-audio-bridge.git](https://github.com/yourusername/discord-audio-bridge.git)
cd discord-audio-bridge

```


2. **Install Dependencies:**
```bash
# Using uv (Recommended)
uv sync

# Using pip
pip install -r requirements.txt

```


3. **Configuration:**
Create a `.env` file in the root directory:
```bash
DISCORD_TOKEN=your_bot_token_here
```



---

## ⚡ Quick Start

### 1. Start the Bridge

Run the main entry point to initialize the bot and create the pipes.

```bash
uv run src/main.py

```

*You should see logs indicating the bot has connected and the "Heartbeat" is active.*

### 2. Stream Audio (Speaker)

You can pipe any audio into the bridge using FFmpeg.

```bash
ffmpeg -re -i my_music.mp3 -f s16le -ar 48000 -ac 2 -y /tmp/discord_speaker_input.pcm

```

### 3. Record Audio (Listener)

Read raw PCM data from the output pipe.

```bash
cat /tmp/discord_listener_output.pcm > recording.pcm
# Play back with ffplay
ffplay -f s16le -ar 48000 -ch_layout stereo recording.pcm

```

---

## 🧪 Testing

The project includes a comprehensive test suite to verify the pipeline without external dependencies.

```bash
# Test Speaker (Generates a 440Hz Sine Wave)
uv run test_bridge.py speaker

# Test Listener (Records 5 seconds of voice)
uv run test_bridge.py listener

```

---

## 🎧 Advanced Usage: VLC Integration

You can use VLC as a high-quality "DJ Console" to mix and stream local files. The included helper script generates the complex CLI commands for you.

**Generate a command to play a playlist in background mode:**

```bash
uv run vlc_helper.py --source "playlist.m3u" --mute_local --headless

```

**Run it directly:**

```bash
# Example: Pipe system audio or file via VLC
/Applications/VLC.app/Contents/MacOS/VLC --sout='#transcode{acodec=s16l,channels=2,samplerate=48000}:std{access=file,mux=raw,dst=/tmp/discord_speaker_input.pcm}'

```

---

## 📂 Project Structure

```text
.
├── discord_bridge/         # Main Package
│   ├── __init__.py         # Public API Facade
│   ├── core.py             # Bot Singleton & Connection Logic
│   ├── infrastructure.py   # OS Pipe Management
│   ├── components.py       # Audio Sinks & Lazy Loading
│   └── patch.py            # Opus Fault Tolerance
├── src/
│   └── main.py             # Entry point example
├── test_bridge.py          # End-to-End Test Suite
├── vlc_helper.py           # VLC Command Generator
└── pyproject.toml          # Dependency Config

```

## 🤝 Contributing

1. Fork the repo.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'Add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.