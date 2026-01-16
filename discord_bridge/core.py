import threading
import asyncio
import logging
import discord
from discord.ext import commands, voice_recv
from .infrastructure import PipeManager
from .components import LazyPipeSink
from .patch import apply_fault_tolerance

log = logging.getLogger(__name__)


class BridgeBot(commands.Bot):
    """Singleton Bot that manages the voice connection."""

    _instance = None

    def __new__(cls, token: str, pipes: PipeManager):
        if cls._instance is None:
            intents = discord.Intents.default()
            intents.message_content = True

            cls._instance = super(BridgeBot, cls).__new__(cls)
            commands.Bot.__init__(cls._instance, command_prefix="!", intents=intents)

            cls._instance._init_singleton(token, pipes)
        return cls._instance

    def __init__(self, token: str, pipes: PipeManager):
        pass

    def _init_singleton(self, token: str, pipes: PipeManager):
        apply_fault_tolerance()
        self.token = token
        self.pipes = pipes
        self.voice_client = None
        self._ready_event = threading.Event()

        # Start background thread
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        # Load Opus library
        try:
            discord.opus.load_opus("/opt/homebrew/lib/libopus.dylib")
        except Exception:
            log.warning("System libopus not found, trying default.")

        asyncio.run(self._async_start())

    async def _async_start(self):
        await self.start(self.token)

    async def on_ready(self):
        log.info(f"🤖 Bot Connected: {self.user}")
        self._ready_event.set()

    async def connect_and_bridge(self, channel_id: int):
        """Joins channel and sets up the bidirectional bridge."""
        channel = self.get_channel(channel_id)
        if not channel:
            raise ValueError(f"Channel {channel_id} not found")

        vc = await channel.connect(cls=voice_recv.VoiceRecvClient)
        self.voice_client = vc
        log.info(f"🔗 Connected to Voice Channel: {channel.name}")
        # --- PATH 1: SPEAKER (Mixer & Heartbeat) ---
        # Input 0: Infinite Silence (Heartbeat)
        # Input 1: Speaker Pipe (Music)
        ffmpeg_opts = {
            "before_options": "-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=48000 -f s16le -ar 48000 -ac 2",
            "options": '-filter_complex "[0:a][1:a]amix=inputs=2:duration=first:dropout_transition=2[a]" -map "[a]"',
        }

        source = discord.FFmpegPCMAudio(self.pipes.speaker_path, **ffmpeg_opts)
        vc.play(source)
        log.info("🎤 Speaker Bridge Active (Heartbeat Enabled)")

        # --- PATH 2: LISTENER (Capture) ---
        vc.listen(LazyPipeSink(self.pipes.listener_path))
        log.info("👂 Listener Bridge Active")

    async def disconnect_bridge(self):
        """Cleanly disconnects voice and stops FFmpeg."""
        if self.voice_client and self.voice_client.is_connected():
            log.info("🔌 Disconnecting Voice Bridge...")
            await self.voice_client.disconnect()
            # This kills the FFmpeg subprocess gracefully
