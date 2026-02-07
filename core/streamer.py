"""
ART'TERYX Core - Zero-Disk Telegram Streamer
=============================================
Async streaming upload directly to Telegram Cloud.
"""

import asyncio
import io
import os
from typing import Optional, Callable
from pyrogram import Client
from pyrogram.types import Message


class TelegramStreamer:
    """
    Zero-disk streaming uploader for Telegram.
    
    Features:
    - Direct BytesIO → Telegram upload (no disk write)
    - Async Pyrogram client for high performance
    - Progress callbacks for UI updates
    - Automatic chunked upload for large files
    """

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        bot_token: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ):
        """
        Initialize Telegram streamer.

        Args:
            api_id: Telegram API ID from my.telegram.org
            api_hash: Telegram API Hash from my.telegram.org
            bot_token: Bot token from @BotFather
            progress_callback: Callback(uploaded_bytes, total_bytes)
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.bot_token = bot_token
        self.progress_callback = progress_callback
        self._client: Optional[Client] = None

    async def _get_client(self) -> Client:
        """Get or create Pyrogram client."""
        if self._client is None:
            self._client = Client(
                name="art_teryx_streamer",
                api_id=self.api_id,
                api_hash=self.api_hash,
                bot_token=self.bot_token,
                in_memory=True,  # No session file on disk
            )
        
        if not self._client.is_connected:
            await self._client.start()
        
        return self._client

    async def upload_video(
        self,
        chat_id: int | str,
        buffer: io.BytesIO,
        filename: str,
        caption: str = "",
        message_thread_id: Optional[int] = None,
        thumb: Optional[bytes] = None,
        duration: int = 0,
        width: int = 0,
        height: int = 0,
        supports_streaming: bool = True,
        protect_content: bool = False,
    ) -> Message:
        """
        Upload video from memory buffer to Telegram.

        Args:
            chat_id: Target chat/group ID
            buffer: BytesIO buffer containing video data
            filename: Display filename
            caption: Video caption (HTML supported)
            message_thread_id: Forum topic ID (optional)
            thumb: Thumbnail bytes (optional)
            duration: Video duration in seconds
            width: Video width
            height: Video height
            supports_streaming: Enable streaming playback
            protect_content: Prevent forwarding/saving

        Returns:
            Sent Message object
        """
        client = await self._get_client()

        # Ensure buffer is at start
        buffer.seek(0)

        # Create progress wrapper
        def progress_wrapper(current: int, total: int):
            if self.progress_callback:
                self.progress_callback(current, total)

        # Upload video
        message = await client.send_video(
            chat_id=chat_id,
            video=buffer,
            caption=caption,
            parse_mode="html",
            file_name=filename,
            thumb=thumb,
            duration=duration,
            width=width,
            height=height,
            supports_streaming=supports_streaming,
            protect_content=protect_content,
            message_thread_id=message_thread_id,
            progress=progress_wrapper,
        )

        return message

    async def upload_document(
        self,
        chat_id: int | str,
        buffer: io.BytesIO,
        filename: str,
        caption: str = "",
        message_thread_id: Optional[int] = None,
        thumb: Optional[bytes] = None,
        protect_content: bool = False,
    ) -> Message:
        """
        Upload document from memory buffer to Telegram.

        Args:
            chat_id: Target chat/group ID
            buffer: BytesIO buffer containing file data
            filename: Display filename
            caption: Document caption
            message_thread_id: Forum topic ID (optional)
            thumb: Thumbnail bytes (optional)
            protect_content: Prevent forwarding/saving

        Returns:
            Sent Message object
        """
        client = await self._get_client()
        buffer.seek(0)

        def progress_wrapper(current: int, total: int):
            if self.progress_callback:
                self.progress_callback(current, total)

        message = await client.send_document(
            chat_id=chat_id,
            document=buffer,
            caption=caption,
            parse_mode="html",
            file_name=filename,
            thumb=thumb,
            protect_content=protect_content,
            message_thread_id=message_thread_id,
            progress=progress_wrapper,
        )

        return message

    async def create_forum_topic(
        self,
        chat_id: int | str,
        name: str,
        icon_color: int = 16711680,  # Red
    ) -> int:
        """
        Create a forum topic in a supergroup.

        Args:
            chat_id: Supergroup chat ID
            name: Topic name
            icon_color: Topic icon color

        Returns:
            Topic message_thread_id
        """
        client = await self._get_client()
        
        topic = await client.create_forum_topic(
            chat_id=chat_id,
            title=name,
            icon_color=icon_color,
        )
        
        return topic.id

    async def delete_forum_topic(self, chat_id: int | str, topic_id: int) -> bool:
        """Delete a forum topic."""
        client = await self._get_client()
        try:
            await client.delete_forum_topic(chat_id=chat_id, message_thread_id=topic_id)
            return True
        except Exception:
            return False

    async def delete_message(self, chat_id: int | str, message_id: int) -> bool:
        """Delete a message."""
        client = await self._get_client()
        try:
            await client.delete_messages(chat_id=chat_id, message_ids=message_id)
            return True
        except Exception:
            return False

    async def copy_message(
        self,
        chat_id: int | str,
        from_chat_id: int | str,
        message_id: int,
        protect_content: bool = False,
        reply_markup=None,
    ) -> Message:
        """Copy a message to another chat."""
        client = await self._get_client()
        
        return await client.copy_message(
            chat_id=chat_id,
            from_chat_id=from_chat_id,
            message_id=message_id,
            protect_content=protect_content,
            reply_markup=reply_markup,
        )

    async def close(self):
        """Close the Pyrogram client."""
        if self._client and self._client.is_connected:
            await self._client.stop()
            self._client = None


# Singleton instance for reuse
_streamer_instance: Optional[TelegramStreamer] = None


def get_streamer() -> TelegramStreamer:
    """Get the global TelegramStreamer instance."""
    global _streamer_instance
    
    if _streamer_instance is None:
        api_id = int(os.getenv("API_ID", "0"))
        api_hash = os.getenv("API_HASH", "")
        bot_token = os.getenv("BOT_TOKEN", "")
        
        if not all([api_id, api_hash, bot_token]):
            raise RuntimeError(
                "Missing Telegram credentials. "
                "Set API_ID, API_HASH, and BOT_TOKEN in .env"
            )
        
        _streamer_instance = TelegramStreamer(
            api_id=api_id,
            api_hash=api_hash,
            bot_token=bot_token,
        )
    
    return _streamer_instance


async def upload_buffer_to_telegram(
    chat_id: int | str,
    buffer: io.BytesIO,
    filename: str,
    caption: str = "",
    message_thread_id: Optional[int] = None,
    progress_callback: Optional[Callable] = None,
) -> Message:
    """
    Convenience function to upload a buffer to Telegram.

    Args:
        chat_id: Target chat ID
        buffer: BytesIO buffer
        filename: Display filename
        caption: Message caption
        message_thread_id: Forum topic ID
        progress_callback: Upload progress callback

    Returns:
        Sent Message object
    """
    streamer = get_streamer()
    streamer.progress_callback = progress_callback
    
    # Determine if video or document based on extension
    ext = filename.lower().split(".")[-1] if "." in filename else ""
    video_exts = {"mp4", "mkv", "webm", "avi", "mov", "m4v"}
    
    if ext in video_exts:
        return await streamer.upload_video(
            chat_id=chat_id,
            buffer=buffer,
            filename=filename,
            caption=caption,
            message_thread_id=message_thread_id,
        )
    else:
        return await streamer.upload_document(
            chat_id=chat_id,
            buffer=buffer,
            filename=filename,
            caption=caption,
            message_thread_id=message_thread_id,
        )
