"""
ART'TERYX Plugin - Instagram Handler
====================================
Async Instagram video/reel downloader using yt-dlp.
"""

import io
import os
import re
import asyncio
import tempfile
from typing import Optional, Callable
from dataclasses import dataclass
from yt_dlp import YoutubeDL


@dataclass
class InstagramResult:
    """Result of Instagram download."""
    buffer: io.BytesIO
    filename: str
    title: str
    description: str
    duration: int
    source_url: str
    source_username: Optional[str]


class InstagramHandler:
    """
    Instagram video/reel downloader using yt-dlp.
    
    Features:
    - Cookie-based authentication (required for most content)
    - Reels, posts, stories support
    - Best quality video selection
    """

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """
        Initialize Instagram handler.

        Args:
            cookies_file: Path to cookies.txt file (highly recommended)
            progress_callback: Progress callback function
        """
        self.cookies_file = cookies_file
        self.progress_callback = progress_callback

    async def download(self, url: str) -> InstagramResult:
        """
        Download Instagram video to memory buffer.

        Args:
            url: Instagram video/reel URL

        Returns:
            InstagramResult with BytesIO buffer and metadata
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._download_sync, url)

    def _download_sync(self, url: str) -> InstagramResult:
        """Synchronous download using yt-dlp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "%(title).80s.%(ext)s")

            ydl_opts = {
                "outtmpl": output_template,
                "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
                "merge_output_format": "mp4",
                "noplaylist": True,
                "retries": 5,
                "fragment_retries": 5,
                "socket_timeout": 30,
                "nopart": True,
                "http_headers": {
                    "User-Agent": self.USER_AGENT,
                    "Referer": "https://www.instagram.com/",
                },
                "quiet": True,
                "no_warnings": True,
            }

            if self.cookies_file and os.path.exists(self.cookies_file):
                ydl_opts["cookiefile"] = self.cookies_file

            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                downloaded_file = ydl.prepare_filename(info)

                # Handle merged output
                if not os.path.exists(downloaded_file):
                    base = os.path.splitext(downloaded_file)[0]
                    downloaded_file = base + ".mp4"

                # Read to memory
                buffer = io.BytesIO()
                with open(downloaded_file, "rb") as f:
                    buffer.write(f.read())
                buffer.seek(0)

                filename = os.path.basename(downloaded_file)

                return InstagramResult(
                    buffer=buffer,
                    filename=filename,
                    title=info.get("title", "Instagram Video"),
                    description=info.get("description") or info.get("title", ""),
                    duration=info.get("duration", 0),
                    source_url=info.get("webpage_url") or url,
                    source_username=info.get("uploader_id") or info.get("uploader"),
                )


async def download_instagram(
    url: str,
    cookies_file: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> InstagramResult:
    """
    Convenience function to download Instagram video.

    Args:
        url: Instagram video/reel URL
        cookies_file: Optional cookies file path
        progress_callback: Progress callback function

    Returns:
        InstagramResult with BytesIO buffer
    """
    handler = InstagramHandler(
        cookies_file=cookies_file,
        progress_callback=progress_callback
    )
    return await handler.download(url)


def is_instagram_url(url: str) -> bool:
    """Check if URL is an Instagram URL."""
    url_lower = (url or "").lower()
    return any(
        domain in url_lower
        for domain in ["instagram.com", "instagr.am"]
    )
