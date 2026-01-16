pipe to stream
```bash
ffmpeg -re -i zoo.mp3 -f s16le -ar 48000 -ac 2 -y /tmp/discord_vlc_pipe
```

```bash
/Applications/VLC.app/Contents/MacOS/VLC \
--sout='#duplicate{dst=display,dst="transcode{acodec=s16l,channels=2,samplerate=48000}:afilter=gain{gain=0.5}:std{access=file,mux=raw,dst=/tmp/discord_vlc_pipe}"}'
```