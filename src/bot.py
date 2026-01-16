"""Module for managing Discord music bot operations with decoupled architecture."""

import asyncio
import collections
from dataclasses import dataclass
import logging
from typing import Any, cast, Optional, Dict, List, Deque
import os

import discord
from discord.ext import commands
import yt_dlp
from loguru import logger as log


# ==========================================
# Logging Configuration
# ==========================================


class InterceptHandler(logging.Handler):
    """Logs standard library events through Loguru."""

    def emit(self, record):
        try:
            level = log.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_logging():
    """Configures discord.py and yt-dlp to use Loguru."""
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)


# ==========================================
# Domain Models
# ==========================================


@dataclass
class MusicTrack:
    """Base representation of a music track."""

    title: str
    url: str
    duration: int

    def __str__(self):
        return (
            f"MusicTrack(title={self.title}, url={self.url}, duration={self.duration})"
        )


@dataclass
class YoutubeVideo(MusicTrack):
    """Representation of a YouTube video track."""

    uploader: str
    thumbnail: str
    data: Any

    def __init__(self, info: Any):
        super().__init__(
            title=info.get("title", "Unknown Title"),
            url=info.get("url", ""),
            duration=info.get("duration", 0),
        )
        self.uploader = info.get("uploader", "Unknown Uploader")
        self.thumbnail = info.get("thumbnail", "")
        self.data = info


# ==========================================
# Data Layer: YoutubeClient
# ==========================================


class YoutubeClient:
    """Handles YouTube data extraction using yt-dlp.

    This class is agnostic of Discord and can be used in other contexts (e.g., FastAPI).
    """

    def __init__(self):
        """Initializes the yt-dlp client with optimized options."""
        self.ydl_opts = yt_dlp.parse_options(
            {
                "format": "bestaudio",
                "noplaylist": "True",
                "quiet": "True",
                "no_warnings": "True",
                "default_search": "auto",
                "source_address": "0.0.0.0",
                "remote_component": "ejs:github",
            }
        ).ydl_opts
        self.client = yt_dlp.YoutubeDL(self.ydl_opts)

    async def fetch_video_data(self, url: str) -> Optional[YoutubeVideo]:
        """Extracts video metadata from a specific URL."""
        log.debug(f"Fetching metadata for URL: {url}")
        loop = asyncio.get_event_loop()
        try:
            # Run blocking extraction in executor
            info = await loop.run_in_executor(
                None, lambda: self.client.extract_info(url, download=False)
            )
            if not info:
                return None
            return YoutubeVideo(info)
        except Exception as e:
            log.error(f"Extraction failed for {url}: {e}")
            return None

    async def search_videos(self, query: str, limit: int = 5) -> List[YoutubeVideo]:
        """Searches YouTube and returns a list of YoutubeVideo objects."""
        log.debug(f"Searching YouTube for: {query}")
        search_query = f"ytsearch{limit}:{query}"
        loop = asyncio.get_event_loop()
        try:
            info = await loop.run_in_executor(
                None, lambda: self.client.extract_info(search_query, download=False)
            )
            videos = []
            if not info:
                return videos

            entries = info.get("entries", [])
            for entry in entries:
                if entry:
                    videos.append(YoutubeVideo(entry))
            return videos
        except Exception as e:
            log.error(f"Search failed for {query}: {e}")
            return []


# ==========================================
# Logic Layer: MusicManager
# ==========================================


class MusicManager:
    """Manages the music queue and playback state.

    This class is agnostic of Discord's VoiceClients or Contexts.
    """

    def __init__(self):
        """Initializes the queue storage."""
        # Key: Guild ID (int), Value: Deque of YoutubeVideo
        self._queues: Dict[int, Deque[YoutubeVideo]] = {}

    def get_queue(self, guild_id: int) -> Deque[YoutubeVideo]:
        """Retrieves or creates the queue for a specific guild."""
        if guild_id not in self._queues:
            self._queues[guild_id] = collections.deque()
        return self._queues[guild_id]

    def add_to_queue(self, guild_id: int, track: YoutubeVideo) -> int:
        """Adds a track to the guild's queue. Returns new queue size."""
        queue = self.get_queue(guild_id)
        queue.append(track)
        log.debug(
            f"Added {track.title} to queue for guild {guild_id}. Queue size: {len(queue)}"
        )
        return len(queue)

    def get_next_track(self, guild_id: int) -> Optional[YoutubeVideo]:
        """Removes and returns the next track from the queue."""
        queue = self.get_queue(guild_id)
        if not queue:
            return None
        return queue.popleft()

    def is_queue_empty(self, guild_id: int) -> bool:
        """Checks if the queue for a guild is empty."""
        return not self.get_queue(guild_id)

    def clear_queue(self, guild_id: int):
        """Clears the queue for a specific guild."""
        if guild_id in self._queues:
            self._queues[guild_id].clear()


# ==========================================
# Presentation Layer: DiscordManager
# ==========================================


class DiscordManager(commands.Cog):
    """Handles Discord-specific interactions, voice connections, and audio streaming."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.music_manager = MusicManager()
        self.youtube_client = YoutubeClient()

        # UI State for reaction menus (Message ID -> List of Videos)
        self.pending_selections: Dict[int, List[YoutubeVideo]] = {}

    def _create_audio_source(self, track: YoutubeVideo) -> discord.FFmpegPCMAudio:
        """Creates a Discord-compatible FFmpeg audio source from a track."""
        # TODO: Move FFmpeg options to a config file
        return discord.FFmpegPCMAudio(
            track.url,
            options="-vn",
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        )

    async def _play_next(self, guild: discord.Guild, voice_client: discord.VoiceClient):
        """Internal logic to fetch the next track and play it recursively."""
        if not voice_client:
            return

        next_track = self.music_manager.get_next_track(guild.id)

        if not next_track:
            log.info(f"Queue empty for guild {guild.id}, playback finished.")
            return

        log.debug(f"Preparing to play: {next_track.title}")

        try:
            audio_source = self._create_audio_source(next_track)

            def after_playing(error):
                if error:
                    log.error(f"Error in playback: {error}")

                # Schedule the next track on the main event loop
                future = asyncio.run_coroutine_threadsafe(
                    self._play_next(guild, voice_client), self.bot.loop
                )
                try:
                    future.result()
                except Exception as e:
                    # Generic catch for future result errors to prevent crash
                    log.error(f"Error scheduling next track: {e}")

            voice_client.play(audio_source, after=after_playing)
            log.info(f"Now playing: {next_track.title}")

        except Exception as e:
            log.error(f"Failed to play track {next_track.title}: {e}")
            # Try next track if this one fails
            await self._play_next(guild, voice_client)

    async def _ensure_voice_connection(
        self, ctx: commands.Context
    ) -> Optional[discord.VoiceClient]:
        """Connects to the author's voice channel if not already connected."""
        author = cast(discord.Member, ctx.author)
        if not author.voice or not author.voice.channel:
            await ctx.send("You must be in a voice channel.")
            return None

        target_channel = author.voice.channel
        voice_client = cast(discord.VoiceClient, ctx.voice_client)

        if not voice_client:
            voice_client = await target_channel.connect()
            await ctx.send(f"Connected to {target_channel.name}")
        elif voice_client.channel.id != target_channel.id:
            await voice_client.move_to(target_channel)
            await ctx.send(f"Moved to {target_channel.name}")

        return voice_client

    async def _handle_search_selection(self, ctx: commands.Context, query: str):
        """Handles the search UI flow."""
        results = await self.youtube_client.search_videos(query)
        if not results:
            await ctx.send("No results found.")
            return

        # Build selection message
        msg_content = "Select a track:\n"
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        valid_results = results[:5]

        for i, vid in enumerate(valid_results):
            msg_content += f"{emojis[i]} {vid.title} ({vid.uploader})\n"

        message = await ctx.send(msg_content)
        self.pending_selections[message.id] = valid_results

        for emoji in emojis[: len(valid_results)]:
            await message.add_reaction(emoji)

    @commands.command(name="play")
    async def play(self, ctx: commands.Context, *, query: str):
        """Command to play music by URL or search query."""
        voice_client = await self._ensure_voice_connection(ctx)
        if not voice_client:
            return

        guild_id = ctx.guild.id

        # Determine if URL or Search
        if query.startswith("http"):
            track = await self.youtube_client.fetch_video_data(query)
            if not track:
                await ctx.send("Invalid URL or extraction failed.")
                return

            self.music_manager.add_to_queue(guild_id, track)
            await ctx.send(f"Queued: {track.title}")

            # Start playback if not already playing
            if not voice_client.is_playing():
                await self._play_next(ctx.guild, voice_client)
        else:
            await self._handle_search_selection(ctx, query)

    @commands.command(name="skip")
    async def skip(self, ctx: commands.Context):
        """Skips the current track."""
        voice_client = cast(discord.VoiceClient, ctx.voice_client)
        if voice_client and voice_client.is_playing():
            voice_client.stop()  # Triggers 'after' callback which plays next
            await ctx.send("Skipped.")

    @commands.command(name="queue")
    async def show_queue(self, ctx: commands.Context):
        """Displays the current queue."""
        queue = self.music_manager.get_queue(ctx.guild.id)
        if not queue:
            await ctx.send("Queue is empty.")
            return

        msg = "**Current Queue:**\n"
        for i, track in enumerate(queue):
            msg += f"{i + 1}. {track.title}\n"
        await ctx.send(msg)

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        """Handles user selection from search results."""
        if user.bot:
            return

        message_id = reaction.message.id
        if message_id not in self.pending_selections:
            return

        options = self.pending_selections[message_id]
        emoji_map = {"1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3, "5️⃣": 4}

        idx = emoji_map.get(str(reaction.emoji))
        if idx is None or idx >= len(options):
            return

        selected_track = options[idx]
        guild = reaction.message.guild

        if guild:
            self.music_manager.add_to_queue(guild.id, selected_track)
            await reaction.message.channel.send(
                f"Selected and queued: {selected_track.title}"
            )

            voice_client = cast(discord.VoiceClient, guild.voice_client)
            if voice_client and not voice_client.is_playing():
                await self._play_next(guild, voice_client)

        # Cleanup
        del self.pending_selections[message_id]
        try:
            await reaction.message.delete()
        except discord.Forbidden:
            pass  # Lack permissions to delete

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error):
        log.error(f"Command error in {ctx.command}: {error}")


# ==========================================
# Main Application Entry
# ==========================================


async def main():
    setup_logging()

    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        log.error("DISCORD_BOT_TOKEN environment variable not set.")
        return

    # Load Opus (Audio Codec)
    # TODO: Make path configurable via env var
    opus_path = "/opt/homebrew/Cellar/opus/1.6/lib/libopus.0.dylib"
    if not discord.opus.is_loaded():
        try:
            discord.opus.load_opus(opus_path)
        except Exception:
            # Fallback for Linux/Docker environments where it might be auto-loaded
            pass

    if not discord.opus.is_loaded():
        log.warning("Opus library not loaded. Audio may fail.")

    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix=commands.when_mentioned_or("!"),
        description="Refactored Discord Music Bot",
        intents=intents,
    )

    async with bot:
        await bot.add_cog(DiscordManager(bot))
        log.info("Starting bot...")
        await bot.start(token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Handle graceful shutdown on Ctrl+C
        log.info("Bot stopped by user.")
