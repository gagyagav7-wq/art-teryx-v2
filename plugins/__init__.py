"""
ART'TERYX Plugins - Platform Handlers
=====================================
Modular handlers for different media platforms.
"""

from .tiktok import TikTokHandler, download_tiktok
from .twitter import TwitterHandler, download_twitter
from .instagram import InstagramHandler, download_instagram
from .facebook import FacebookHandler, download_facebook
from .universal import UniversalHandler, download_universal

__all__ = [
    "TikTokHandler",
    "TwitterHandler",
    "InstagramHandler",
    "FacebookHandler",
    "UniversalHandler",
    "download_tiktok",
    "download_twitter",
    "download_instagram",
    "download_facebook",
    "download_universal",
]
