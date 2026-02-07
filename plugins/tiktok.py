"""
ART'TERYX Plugin - TikTok Handler
=================================
Async TikTok video downloader using TikWM API.
"""

import io
import re
import asyncio
import aiohttp
from typing import Optional, Callable
from dataclasses import dataclass


@dataclass
class TikTokResult:
    """Result of TikTok download."""
    buffer: io.BytesIO
    filename: str
    title: str
    description: str
    duration: int
    source_url: str
    source_username: Optional[str]


class TikTokHandler:
    """
    TikTok video downloader using TikWM API.
    
    Features:
    - HD video download
    - Zero-disk memory buffer
    - Progress callbacks
    - Metadata extraction
    """

    API_URL = "https://www.tikwm.com/api/"
    TIMEOUT = aiohttp.ClientTimeout(total=120, connect=30)

    def __init__(self, progress_callback: Optional[Callable[[int, int], None]] = None):
        """
        Initialize TikTok handler.

        Args:
            progress_callback: Callback(downloaded_bytes, total_bytes)
        """
        self.progress_callback = progress_callback

    async def download(self, url: str) -> TikTokResult:
        """
        Download TikTok video to memory buffer.

        Args:
            url: TikTok video URL

        Returns:
            TikTokResult with BytesIO buffer and metadata
        """
        async with aiohttp.ClientSession(timeout=self.TIMEOUT) as session:
            # Get video info from API
            info = await self._get_video_info(session, url)

            # Download video to memory
            buffer = await self._download_video(session, info["video_url"])

            # Clean title for filename
            clean_title = self._sanitize_filename(info["title"])
            filename = f"{clean_title}.mp4"

            return TikTokResult(
                buffer=buffer,
                filename=filename,
                title=info["title"],
                description=info["title"],
                duration=info["duration"],
                source_url=info["source_url"],
                source_username=info["username"],
            )

    async def _get_video_info(self, session: aiohttp.ClientSession, url: str) -> dict:
        """Get video info from TikWM API."""
        params = {"url": url, "hd": 1}

        async with session.get(self.API_URL, params=params) as resp:
            data = await resp.json()

            if data.get("code") != 0:
                raise Exception(f"TikWM API Error: {data.get('msg', 'Unknown error')}")

            video_data = data["data"]

            # Prefer HD if available
            video_url = video_data.get("hdplay") or video_data.get("play")
            if not video_url:
                raise Exception("No video URL found in API response")

            # Extract author info
            author = video_data.get("author") or {}
            username = (
                author.get("unique_id")
                or author.get("username")
                or author.get("name")
            )

            return {
                "video_url": video_url,
                "title": video_data.get("title", "TikTok Video"),
                "duration": video_data.get("duration", 0),
                "source_url": author.get("url") or url,
                "username": username,
            }

    async def _download_video(self, session: aiohttp.ClientSession, url: str) -> io.BytesIO:
        """Download video to memory buffer."""
        buffer = io.BytesIO()
        downloaded = 0

        async with session.get(url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))

            async for chunk in resp.content.iter_chunked(1024 * 1024):
                buffer.write(chunk)
                downloaded += len(chunk)

                if self.progress_callback and total > 0:
                    self.progress_callback(downloaded, total)

        buffer.seek(0)
        return buffer

    def _sanitize_filename(self, title: str, max_length: int = 50) -> str:
        """Sanitize title for use as filename."""
        # Remove special characters
        clean = re.sub(r'[^\w\s-]', '', title).strip()
        # Replace spaces with underscores
        clean = clean.replace(' ', '_')
        # Truncate
        clean = clean[:max_length]
        # Fallback
        return clean or "tiktok_video"


async def download_tiktok(
    url: str,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> TikTokResult:
    """
    Convenience function to download TikTok video.

    Args:
        url: TikTok video URL
        progress_callback: Progress callback function

    Returns:
        TikTokResult with BytesIO buffer
    """
    handler = TikTokHandler(progress_callback=progress_callback)
    return await handler.download(url)


def is_tiktok_url(url: str) -> bool:
    """Check if URL is a TikTok URL."""
    url_lower = (url or "").lower()
    return any(
        domain in url_lower
        for domain in ["tiktok.com", "vt.tiktok.com", "vm.tiktok.com"]
    )
