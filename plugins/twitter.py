"""
ART'TERYX Plugin - Twitter/X Handler
=====================================
Async Twitter/X video downloader using yt-dlp.
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
class TwitterResult:
    """Result of Twitter download."""
    buffer: io.BytesIO
    filename: str
    title: str
    description: str
    duration: int
    source_url: str
    source_username: Optional[str]


class TwitterHandler:
    """
    Twitter/X video downloader using yt-dlp.
    
    Features:
    - Cookie-based authentication support
    - Best quality video selection
    - Async wrapper around yt-dlp
    """

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"

    def __init__(
        self,
        cookies_file: Optional[str] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """
        Initialize Twitter handler.

        Args:
            cookies_file: Path to cookies.txt file
            progress_callback: Progress callback function
        """
        self.cookies_file = cookies_file
        self.progress_callback = progress_callback

    async def download(self, url: str) -> TwitterResult:
        """
        Download Twitter video to memory buffer.

        Args:
            url: Twitter/X video URL

        Returns:
            TwitterResult with BytesIO buffer and metadata
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._download_sync, url)

    def _download_sync(self, url: str) -> TwitterResult:
        """Synchronous download using yt-dlp."""
        # Use temp file then read to memory
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "%(title).80s.%(ext)s")

            ydl_opts = {
                "outtmpl": output_template,
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "noplaylist": True,
                "retries": 5,
                "fragment_retries": 5,
                "socket_timeout": 30,
                "nopart": True,
                "http_headers": {
                    "User-Agent": self.USER_AGENT,
                    "Referer": "https://x.com/",
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
                    # Try with .mp4 extension
                    base = os.path.splitext(downloaded_file)[0]
                    downloaded_file = base + ".mp4"

                # Read file to memory buffer
                buffer = io.BytesIO()
                with open(downloaded_file, "rb") as f:
                    buffer.write(f.read())
                buffer.seek(0)

                filename = os.path.basename(downloaded_file)

                return TwitterResult(
                    buffer=buffer,
                    filename=filename,
                    title=info.get("title", "Twitter Video"),
                    description=info.get("description") or info.get("title", ""),
                    duration=info.get("duration", 0),
                    source_url=info.get("webpage_url") or url,
                    source_username=info.get("uploader_id") or info.get("uploader"),
                )


async def download_twitter(
    url: str,
    cookies_file: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> TwitterResult:
    """
    Convenience function to download Twitter video.

    Args:
        url: Twitter/X video URL
        cookies_file: Optional cookies file path
        progress_callback: Progress callback function

    Returns:
        TwitterResult with BytesIO buffer
    """
    handler = TwitterHandler(
        cookies_file=cookies_file,
        progress_callback=progress_callback
    )
    return await handler.download(url)


def is_twitter_url(url: str) -> bool:
    """Check if URL is a Twitter/X URL."""
    url_lower = (url or "").lower()
    return any(
        domain in url_lower
        for domain in ["twitter.com", "x.com", "t.co"]
    )
