"""
ART'TERYX Core - Aria2-Style Multi-Connection Downloader
=========================================================
High-performance async download engine with parallel chunk fetching.
"""

import asyncio
import aiohttp
import io
from typing import Callable, Optional
from dataclasses import dataclass


@dataclass
class DownloadResult:
    """Result of a download operation."""
    buffer: io.BytesIO
    filename: str
    content_type: str
    size: int
    metadata: dict


class MultiConnectionDownloader:
    """
    Aria2-style multi-connection download engine.
    
    Features:
    - Parallel chunk downloads (configurable connections)
    - Memory-only buffering (zero-disk)
    - Progress callbacks for UI updates
    - Automatic retry with exponential backoff
    """

    DEFAULT_CONNECTIONS = 8
    MAX_CONNECTIONS = 16
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks
    MAX_RETRIES = 3
    TIMEOUT = aiohttp.ClientTimeout(total=300, connect=30)

    def __init__(
        self,
        connections: int = DEFAULT_CONNECTIONS,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        """
        Initialize downloader.

        Args:
            connections: Number of parallel connections (max 16)
            progress_callback: Callback(downloaded_bytes, total_bytes, speed_str)
        """
        self.connections = min(connections, self.MAX_CONNECTIONS)
        self.progress_callback = progress_callback
        self._downloaded = 0
        self._total = 0
        self._lock = asyncio.Lock()

    async def download(self, url: str, headers: Optional[dict] = None) -> DownloadResult:
        """
        Download file from URL using multi-connection strategy.

        Args:
            url: Direct download URL
            headers: Optional HTTP headers

        Returns:
            DownloadResult with BytesIO buffer and metadata
        """
        headers = headers or {}
        headers.setdefault("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120")

        async with aiohttp.ClientSession(timeout=self.TIMEOUT) as session:
            # Get file info via HEAD request
            file_info = await self._get_file_info(session, url, headers)
            
            self._total = file_info["size"]
            self._downloaded = 0

            # If server doesn't support range requests, fall back to single connection
            if not file_info["supports_range"] or self._total == 0:
                return await self._download_single(session, url, headers, file_info)

            # Multi-connection download
            return await self._download_multi(session, url, headers, file_info)

    async def _get_file_info(
        self, session: aiohttp.ClientSession, url: str, headers: dict
    ) -> dict:
        """Get file metadata via HEAD request."""
        async with session.head(url, headers=headers, allow_redirects=True) as resp:
            content_length = int(resp.headers.get("Content-Length", 0))
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
            accept_ranges = resp.headers.get("Accept-Ranges", "").lower()
            
            # Extract filename from Content-Disposition or URL
            filename = self._extract_filename(resp.headers, url)

            return {
                "size": content_length,
                "content_type": content_type,
                "supports_range": accept_ranges == "bytes" and content_length > 0,
                "filename": filename,
            }

    def _extract_filename(self, headers: dict, url: str) -> str:
        """Extract filename from headers or URL."""
        import re
        from urllib.parse import urlparse, unquote

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

        return "download.mp4"

    async def _download_single(
        self, session: aiohttp.ClientSession, url: str, headers: dict, file_info: dict
    ) -> DownloadResult:
        """Single connection download (fallback)."""
        buffer = io.BytesIO()

        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            async for chunk in resp.content.iter_chunked(self.CHUNK_SIZE):
                buffer.write(chunk)
                await self._update_progress(len(chunk))

        buffer.seek(0)
        return DownloadResult(
            buffer=buffer,
            filename=file_info["filename"],
            content_type=file_info["content_type"],
            size=buffer.getbuffer().nbytes,
            metadata=file_info,
        )

    async def _download_multi(
        self, session: aiohttp.ClientSession, url: str, headers: dict, file_info: dict
    ) -> DownloadResult:
        """Multi-connection parallel download."""
        total_size = file_info["size"]
        
        # Calculate chunk ranges
        chunk_size = max(total_size // self.connections, self.CHUNK_SIZE)
        ranges = []
        
        start = 0
        while start < total_size:
            end = min(start + chunk_size - 1, total_size - 1)
            ranges.append((start, end))
            start = end + 1

        # Download chunks in parallel
        chunks = [None] * len(ranges)
        
        async def download_chunk(idx: int, start: int, end: int):
            for attempt in range(self.MAX_RETRIES):
                try:
                    chunk_headers = {**headers, "Range": f"bytes={start}-{end}"}
                    async with session.get(url, headers=chunk_headers) as resp:
                        if resp.status not in (200, 206):
                            raise aiohttp.ClientError(f"HTTP {resp.status}")
                        
                        data = await resp.read()
                        chunks[idx] = data
                        await self._update_progress(len(data))
                        return
                except Exception as e:
                    if attempt == self.MAX_RETRIES - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

        # Execute parallel downloads
        tasks = [
            download_chunk(idx, start, end)
            for idx, (start, end) in enumerate(ranges)
        ]
        await asyncio.gather(*tasks)

        # Combine chunks into single buffer
        buffer = io.BytesIO()
        for chunk in chunks:
            if chunk:
                buffer.write(chunk)

        buffer.seek(0)
        return DownloadResult(
            buffer=buffer,
            filename=file_info["filename"],
            content_type=file_info["content_type"],
            size=buffer.getbuffer().nbytes,
            metadata=file_info,
        )

    async def _update_progress(self, chunk_size: int):
        """Update download progress."""
        async with self._lock:
            self._downloaded += chunk_size
            if self.progress_callback:
                speed = "calculating..."
                self.progress_callback(self._downloaded, self._total, speed)


async def download_direct_url(
    url: str,
    connections: int = 8,
    progress_callback: Optional[Callable] = None,
    headers: Optional[dict] = None
) -> DownloadResult:
    """
    Convenience function to download a direct URL.

    Args:
        url: Direct download URL
        connections: Number of parallel connections
        progress_callback: Progress callback function
        headers: Optional HTTP headers

    Returns:
        DownloadResult with BytesIO buffer
    """
    downloader = MultiConnectionDownloader(
        connections=connections,
        progress_callback=progress_callback
    )
    return await downloader.download(url, headers)
