"""
ART'TERYX Core - Universal URL Sniffer
======================================
Detect and classify media URLs from any source.
"""

import re
import asyncio
import aiohttp
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse, unquote


class Platform(Enum):
    """Supported platform types."""
    TIKTOK = "tiktok"
    TWITTER = "twitter"
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    YOUTUBE = "youtube"
    DIRECT = "direct"
    UNKNOWN = "unknown"


@dataclass
class URLInfo:
    """Information about a detected URL."""
    url: str
    platform: Platform
    is_media: bool
    content_type: Optional[str]
    filename: Optional[str]
    size: Optional[int]
    supports_range: bool


class URLSniffer:
    """
    Universal URL detector and classifier.
    
    Features:
    - Platform detection (TikTok, Twitter, Instagram, etc.)
    - Direct media link detection via Content-Type
    - Auto filename extraction
    - CDN redirect following
    """

    # Platform URL patterns
    PLATFORM_PATTERNS = {
        Platform.TIKTOK: [
            r"tiktok\.com",
            r"vt\.tiktok\.com",
            r"vm\.tiktok\.com",
        ],
        Platform.TWITTER: [
            r"twitter\.com",
            r"x\.com",
            r"t\.co",
        ],
        Platform.INSTAGRAM: [
            r"instagram\.com",
            r"instagr\.am",
        ],
        Platform.FACEBOOK: [
            r"facebook\.com",
            r"fb\.watch",
            r"fb\.com",
        ],
        Platform.YOUTUBE: [
            r"youtube\.com",
            r"youtu\.be",
        ],
    }

    # Video MIME types
    VIDEO_MIMES = {
        "video/mp4",
        "video/webm",
        "video/x-matroska",
        "video/quicktime",
        "video/x-msvideo",
        "video/x-flv",
        "video/3gpp",
    }

    # Audio MIME types
    AUDIO_MIMES = {
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "audio/wav",
        "audio/webm",
        "audio/aac",
    }

    TIMEOUT = aiohttp.ClientTimeout(total=30, connect=10)

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.TIMEOUT)
        return self._session

    def detect_platform(self, url: str) -> Platform:
        """
        Detect platform from URL string (no network request).

        Args:
            url: URL to analyze

        Returns:
            Detected Platform enum
        """
        url_lower = url.lower()

        for platform, patterns in self.PLATFORM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return platform

        return Platform.UNKNOWN

    async def sniff(self, url: str, headers: Optional[dict] = None) -> URLInfo:
        """
        Analyze URL and detect media type.

        Args:
            url: URL to analyze
            headers: Optional HTTP headers

        Returns:
            URLInfo with detected information
        """
        # First, detect platform
        platform = self.detect_platform(url)

        # For known platforms, we don't need to probe
        if platform != Platform.UNKNOWN:
            return URLInfo(
                url=url,
                platform=platform,
                is_media=True,
                content_type=None,
                filename=None,
                size=None,
                supports_range=False,
            )

        # For unknown URLs, probe with HEAD request
        return await self._probe_url(url, headers)

    async def _probe_url(self, url: str, headers: Optional[dict] = None) -> URLInfo:
        """Probe URL with HEAD request to detect media type."""
        headers = headers or {}
        headers.setdefault(
            "User-Agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120"
        )

        session = await self._get_session()

        try:
            async with session.head(
                url, headers=headers, allow_redirects=True
            ) as resp:
                content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
                content_length = int(resp.headers.get("Content-Length", 0))
                accept_ranges = resp.headers.get("Accept-Ranges", "").lower()

                # Check if media type
                is_media = (
                    content_type in self.VIDEO_MIMES
                    or content_type in self.AUDIO_MIMES
                    or content_type.startswith("video/")
                    or content_type.startswith("audio/")
                )

                # Extract filename
                filename = self._extract_filename(resp.headers, str(resp.url))

                return URLInfo(
                    url=str(resp.url),  # Final URL after redirects
                    platform=Platform.DIRECT if is_media else Platform.UNKNOWN,
                    is_media=is_media,
                    content_type=content_type,
                    filename=filename,
                    size=content_length if content_length > 0 else None,
                    supports_range=accept_ranges == "bytes",
                )

        except Exception as e:
            # On error, return unknown with original URL
            return URLInfo(
                url=url,
                platform=Platform.UNKNOWN,
                is_media=False,
                content_type=None,
                filename=None,
                size=None,
                supports_range=False,
            )

    def _extract_filename(self, headers: dict, url: str) -> Optional[str]:
        """Extract filename from headers or URL."""
        # Try Content-Disposition header
        cd = headers.get("Content-Disposition", "")
        if "filename=" in cd:
            match = re.search(r'filename[*]?=["\']?([^"\';\n]+)', cd)
            if match:
                return unquote(match.group(1).strip())

        # Fall back to URL path
        path = urlparse(url).path
        if path and "/" in path:
            filename = unquote(path.split("/")[-1])
            if "." in filename:
                return filename

        return None

    async def close(self):
        """Close the aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None


# Convenience functions
async def detect_url(url: str) -> URLInfo:
    """
    Detect and analyze a URL.

    Args:
        url: URL to analyze

    Returns:
        URLInfo with detected information
    """
    sniffer = URLSniffer()
    try:
        return await sniffer.sniff(url)
    finally:
        await sniffer.close()


def is_social_media_url(url: str) -> bool:
    """
    Quick check if URL is from a known social media platform.

    Args:
        url: URL to check

    Returns:
        True if from known platform
    """
    sniffer = URLSniffer()
    platform = sniffer.detect_platform(url)
    return platform not in (Platform.UNKNOWN, Platform.DIRECT)


def get_platform(url: str) -> str:
    """
    Get platform name from URL.

    Args:
        url: URL to analyze

    Returns:
        Platform name string
    """
    sniffer = URLSniffer()
    return sniffer.detect_platform(url).value
