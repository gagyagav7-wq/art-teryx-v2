"""
ART'TERYX Plugin - Universal/IDM-Style Handler
==============================================
IDM-style direct link downloader for any media URL.
"""

import io
import os
import asyncio
import tempfile
from typing import Optional, Callable
from dataclasses import dataclass
from urllib.parse import urlparse, unquote

from yt_dlp import YoutubeDL

# Import core components
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.downloader import MultiConnectionDownloader, DownloadResult
from core.sniffer import URLSniffer, Platform


@dataclass
class UniversalResult:
    """Result of universal download."""
    buffer: io.BytesIO
    filename: str
    title: str
    description: str
    duration: int
    source_url: str
    source_username: Optional[str]


class UniversalHandler:
    """
    IDM-style universal downloader for any media URL.
    
    Features:
    - Multi-connection Aria2-style downloads for direct links
    - yt-dlp fallback for unknown platforms
    - Auto filename detection
    - Zero-disk memory buffering
    """

    def __init__(
        self,
        connections: int = 8,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Initialize Universal handler.

        Args:
            connections: Number of parallel connections for direct downloads
            progress_callback: Callback(downloaded, total, speed)
        """
        self.connections = connections
        self.progress_callback = progress_callback

    async def download(self, url: str) -> UniversalResult:
        """
        Download media from any URL.

        Strategy:
        1. Sniff URL to detect type
        2. If direct media link → use multi-connection downloader
        3. If unknown → try yt-dlp

        Args:
            url: Any media URL

        Returns:
            UniversalResult with BytesIO buffer
        """
        # Detect URL type
        sniffer = URLSniffer()
        try:
            url_info = await sniffer.sniff(url)
        finally:
            await sniffer.close()

        # Direct media link → use multi-connection downloader
        if url_info.platform == Platform.DIRECT and url_info.is_media:
            return await self._download_direct(url, url_info)

        # Unknown → try yt-dlp
        return await self._download_ytdlp(url)

    async def _download_direct(self, url: str, url_info) -> UniversalResult:
        """Download direct media link using multi-connection engine."""
        downloader = MultiConnectionDownloader(
            connections=self.connections,
            progress_callback=self.progress_callback
        )

        result: DownloadResult = await downloader.download(url)

        filename = url_info.filename or result.filename
        title = os.path.splitext(filename)[0]

        return UniversalResult(
            buffer=result.buffer,
            filename=filename,
            title=title,
            description=f"Downloaded from {urlparse(url).netloc}",
            duration=0,
            source_url=url,
            source_username=None,
        )

    async def _download_ytdlp(self, url: str) -> UniversalResult:
        """Fallback download using yt-dlp."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._ytdlp_sync, url)

    def _ytdlp_sync(self, url: str) -> UniversalResult:
        """Synchronous yt-dlp download."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "%(title).80s.%(ext)s")

            ydl_opts = {
                "outtmpl": output_template,
                "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "merge_output_format": "mp4",
                "noplaylist": True,
                "retries": 10,
                "fragment_retries": 10,
                "concurrent_fragment_downloads": 5,
                "socket_timeout": 30,
                "nopart": True,
                "quiet": True,
                "no_warnings": True,
            }

            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    downloaded_file = ydl.prepare_filename(info)

                    if not os.path.exists(downloaded_file):
                        base = os.path.splitext(downloaded_file)[0]
                        downloaded_file = base + ".mp4"

                    buffer = io.BytesIO()
                    with open(downloaded_file, "rb") as f:
                        buffer.write(f.read())
                    buffer.seek(0)

                    filename = os.path.basename(downloaded_file)

                    return UniversalResult(
                        buffer=buffer,
                        filename=filename,
                        title=info.get("title", "Video"),
                        description=info.get("description") or info.get("title", ""),
                        duration=info.get("duration", 0),
                        source_url=info.get("webpage_url") or url,
                        source_username=info.get("uploader_id") or info.get("uploader"),
                    )
            except Exception:
                # Final fallback: try as direct download
                raise Exception(f"Unable to download from URL: {url}")


async def download_universal(
    url: str,
    connections: int = 8,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> UniversalResult:
    """
    Convenience function to download from any URL.

    Args:
        url: Any media URL
        connections: Number of parallel connections
        progress_callback: Progress callback function

    Returns:
        UniversalResult with BytesIO buffer
    """
    handler = UniversalHandler(
        connections=connections,
        progress_callback=progress_callback
    )
    return await handler.download(url)
