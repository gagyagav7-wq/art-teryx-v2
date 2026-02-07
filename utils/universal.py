import os
from yt_dlp import YoutubeDL

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

COOKIES_IG = os.path.join(BASE_DIR, "cookies_instagram.txt")
COOKIES_X  = os.path.join(BASE_DIR, "cookies_x.txt")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

def _site_headers(url: str) -> dict:
    u = (url or "").lower()
    if "instagram.com" in u:
        return {"User-Agent": UA, "Referer": "https://www.instagram.com/"}
    if "x.com" in u or "twitter.com" in u:
        return {"User-Agent": UA, "Referer": "https://x.com/"}
    return {"User-Agent": UA}

def _pick_cookiefile(url: str) -> str | None:
    u = (url or "").lower()
    if "instagram.com" in u and os.path.exists(COOKIES_IG):
        return COOKIES_IG
    if ("x.com" in u or "twitter.com" in u) and os.path.exists(COOKIES_X):
        return COOKIES_X
    return None

def download_universal(url: str, path: str) -> dict:
    os.makedirs(path, exist_ok=True)

    cookiefile = _pick_cookiefile(url)

    # UPGRADE: Format selection string yang lebih ketat
    # Prioritaskan video resolusi tinggi (up to 1080) dengan codec terbaik (h264/mp4)
    # Ini mencegah download file .m3u8 yang pecah atau file 4K yang bikin berat
    format_str = "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]"

    ydl_opts = {
        # output
        "outtmpl": os.path.join(path, "%(title).80s.%(ext)s"),
        "format": format_str,
        "merge_output_format": "mp4",
        "noplaylist": True,

        # network stability
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 5, # Dipercepat
        "socket_timeout": 30,

        # avoid temp junk
        "nopart": True,
        "continuedl": False,

        # headers
        "http_headers": _site_headers(url),

        # logging
        "quiet": True,
        "no_warnings": True,
        
        # Post-processing bawaan yt-dlp (opsional, tapi kita handle di processor.py)
        "writethumbnail": False,
    }

    if cookiefile:
        ydl_opts["cookiefile"] = cookiefile

    # Khusus Twitter/X kadang butuh fallback format
    u = (url or "").lower()
    if "x.com" in u or "twitter.com" in u:
         ydl_opts["format"] = "bestvideo+bestaudio/best"

    with YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except Exception as e:
            # Fallback jika format specific gagal
            print(f"⚠️ High Quality Download failed, trying default: {e}")
            ydl_opts["format"] = "best"
            with YoutubeDL(ydl_opts) as ydl_fallback:
                info = ydl_fallback.extract_info(url, download=True)

        filename = ydl.prepare_filename(info)
        final_path = filename

        return {
            "path": final_path,
            "title": info.get("title", "Video"),
            "description": info.get("description") or info.get("title") or "—",
            "duration": info.get("duration", 0),
            "filename": os.path.basename(final_path),
            "source_url": info.get("webpage_url") or url,
            "source_username": info.get("uploader_id") or info.get("uploader") or info.get("channel") or None,
        }
