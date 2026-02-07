"""
ART'TERYX Media Downloader - Main Application
==============================================
God-Tier Telegram Media Downloader with Zero-Disk Architecture.

Features:
- Aria2-style multi-connection downloads
- Zero-disk streaming to Telegram Cloud
- Platform-specific handlers (TikTok, Twitter, Instagram, Facebook)
- Universal IDM-style downloader for direct links
"""

import os
import re
import json
import html
import uuid
import asyncio
import threading
import urllib.parse
from pathlib import Path
from typing import Optional, Callable
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================
load_dotenv()
BASE_DIR = Path(__file__).resolve().parent

# Required environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()
BOT_USERNAME = os.getenv("BOT_USERNAME", "").strip()
GROUP_ID = os.getenv("GROUP_ID", "").strip()
WEB_APP_URL = os.getenv("WEB_APP_URL", "").strip()
SECRET_KEY = os.getenv("SECRET_KEY", "art_teryx_secret_key_change_me")

# Admin IDs
ADMIN_IDS = set()
for x in (os.getenv("ADMIN_IDS", "") or "").split(","):
    x = x.strip()
    if x.isdigit():
        ADMIN_IDS.add(int(x))

# Validate required vars
REQUIRED_VARS = {
    "BOT_TOKEN": BOT_TOKEN,
    "BOT_USERNAME": BOT_USERNAME,
    "GROUP_ID": GROUP_ID,
    "WEB_APP_URL": WEB_APP_URL,
}

missing = [k for k, v in REQUIRED_VARS.items() if not v]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

# Cookie file paths
COOKIES_INSTAGRAM = BASE_DIR / "cookies_instagram.txt"
COOKIES_TWITTER = BASE_DIR / "cookies_x.txt"

# Topic map file
TOPIC_MAP_FILE = BASE_DIR / "topic_map.json"


# =============================================================================
# FLASK APPLICATION
# =============================================================================
app = Flask(__name__)
app.secret_key = SECRET_KEY
CORS(app)


# =============================================================================
# GLOBAL ERROR HANDLER
# =============================================================================
class DownloadError(Exception):
    """Custom exception for download errors."""
    pass


@app.errorhandler(Exception)
def handle_error(error):
    """Global error handler - prevents crashes."""
    error_msg = str(error)
    app.logger.error(f"Unhandled error: {error_msg}")
    return jsonify({
        "success": False,
        "error": error_msg,
        "type": type(error).__name__
    }), 500


# =============================================================================
# SECURITY HELPERS
# =============================================================================
BLOCKED_FILES = {
    "app.py", "bot.py", "config.py", "main.py", "topic_map.json",
    "requirements.txt", "Procfile", "runtime.txt", "README.md",
    "__pycache__", "venv", ".git", ".gitignore", ".env",
    "templates", "static", "utils", "downloads", "core", "plugins",
    "cookies.txt", "cookies_instagram.txt", "cookies_x.txt",
}


def sanitize_url(url: str) -> str:
    """Sanitize and validate URL input."""
    url = (url or "").strip()
    
    # Basic URL validation
    if not re.match(r"^https?://", url, re.IGNORECASE):
        raise ValueError("Invalid URL: must start with http:// or https://")
    
    # Check for suspicious patterns
    if any(bad in url.lower() for bad in ["javascript:", "data:", "file:"]):
        raise ValueError("Invalid URL: suspicious protocol detected")
    
    return url


def safe_rel_path(p: str) -> str:
    """Sanitize relative path to prevent directory traversal."""
    p = (p or "").replace("\\", "/").strip()
    p = re.sub(r"/+", "/", p)
    
    # Block directory traversal
    if ".." in p.split("/"):
        raise ValueError("Path traversal not allowed")
    
    return p


def safe_abs_from_rel(rel: str) -> Path:
    """Convert relative path to safe absolute path."""
    rel = safe_rel_path(rel)
    abs_p = (BASE_DIR / rel).resolve()
    
    # Ensure path is within BASE_DIR
    if BASE_DIR not in abs_p.parents and abs_p != BASE_DIR:
        raise ValueError("Path outside allowed directory")
    
    return abs_p


def is_album_level(rel_folder: str) -> bool:
    """Check if path is at album level (DOWNLOADER/PLATFORM/<platform>/<album>)."""
    parts = safe_rel_path(rel_folder).split("/")
    return (
        len(parts) >= 4
        and parts[0].upper() in ("DOWNLOADER", "GALERY")
        and parts[1].upper() == "PLATFORM"
    )


def normalize_storage_folder(rel_folder: str) -> str:
    """Normalize folder path to use DOWNLOADER prefix."""
    rel_folder = safe_rel_path(rel_folder)
    if rel_folder.upper().startswith("GALERY/"):
        rel_folder = "DOWNLOADER/" + rel_folder.split("/", 1)[1]
    return rel_folder


# =============================================================================
# TOPIC MAP MANAGEMENT (THREAD SAFE)
# =============================================================================
topic_lock = threading.Lock()


def load_topic_map() -> dict:
    """Load topic mapping from JSON file."""
    if not TOPIC_MAP_FILE.exists():
        return {}
    try:
        with TOPIC_MAP_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_topic_map(data: dict) -> None:
    """Save topic mapping to JSON file."""
    with TOPIC_MAP_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# =============================================================================
# TELEGRAM API HELPERS (LEGACY SYNC - WILL BE REPLACED)
# =============================================================================
import requests as sync_requests

tg_lock = threading.Lock()


def telegram_create_topic(topic_title: str) -> Optional[int]:
    """Create a forum topic in the target group."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/createForumTopic"
    payload = {
        "chat_id": GROUP_ID,
        "name": topic_title,
        "icon_color": 16711680  # Red
    }
    
    try:
        with tg_lock:
            r = sync_requests.post(url, json=payload, timeout=20)
            res = r.json()
            
            if res.get("ok"):
                return int(res["result"]["message_thread_id"])
            
            app.logger.error(f"Topic creation failed: {res}")
    except Exception as e:
        app.logger.error(f"Topic creation error: {e}")
    
    return None


def telegram_delete_topic(topic_id: int) -> None:
    """Delete a forum topic."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteForumTopic"
    try:
        with tg_lock:
            sync_requests.post(
                url,
                json={"chat_id": GROUP_ID, "message_thread_id": int(topic_id)},
                timeout=20
            )
    except Exception:
        pass


def telegram_delete_message(message_id: int) -> None:
    """Delete a message."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
    try:
        with tg_lock:
            sync_requests.post(
                url,
                json={"chat_id": GROUP_ID, "message_id": int(message_id)},
                timeout=20
            )
    except Exception:
        pass


def ensure_topic_for_folder(rel_folder: str) -> Optional[int]:
    """Ensure a forum topic exists for the given folder."""
    rel_folder = normalize_storage_folder(rel_folder)
    
    with topic_lock:
        mapping = load_topic_map()
        
        # Check existing
        if rel_folder in mapping:
            data = mapping[rel_folder]
            if isinstance(data, dict) and data.get("topic_id"):
                return int(data["topic_id"])
        
        # Create new topic
        parts = rel_folder.split("/")
        if len(parts) < 4:
            return None
        
        platform = parts[2].upper()
        album = parts[3].upper()
        topic_title = f"{platform} | {album}"
        
        topic_id = telegram_create_topic(topic_title)
        if not topic_id:
            return None
        
        mapping[rel_folder] = {"topic_id": topic_id, "messages": {}}
        save_topic_map(mapping)
        
        return topic_id


# =============================================================================
# FOLDER STRUCTURE
# =============================================================================
def auto_fix_structure():
    """Ensure required folder structure exists."""
    for folder in ["DOWNLOADER", "GALERY"]:
        (BASE_DIR / folder).mkdir(parents=True, exist_ok=True)
    
    for root in ["DOWNLOADER", "GALERY"]:
        base = BASE_DIR / root / "PLATFORM"
        base.mkdir(parents=True, exist_ok=True)
        
        for platform in ["TIKTOK", "INSTAGRAM", "TWITTER", "FACEBOOK", "UNIVERSAL"]:
            (base / platform).mkdir(parents=True, exist_ok=True)


# =============================================================================
# CLOUD GALLERY HELPERS
# =============================================================================
def cloud_list_albums(platform_path: str) -> list:
    """List albums from topic_map for a platform path."""
    platform_path = safe_rel_path(platform_path)
    base = normalize_storage_folder(platform_path)
    mapping = load_topic_map()
    
    prefix = base.rstrip("/") + "/"
    seen = set()
    out = []
    
    for k in (mapping or {}).keys():
        if not isinstance(k, str) or not k.startswith(prefix):
            continue
        
        parts = k.split("/")
        if len(parts) < 4:
            continue
        
        album = parts[3]
        if album in seen:
            continue
        seen.add(album)
        
        out.append({
            "name": album,
            "path": f"{platform_path.rstrip('/')}/{album}",
            "type": "folder",
            "icon": "fa-folder",
            "meta": "CLOUD",
        })
    
    return out


def cloud_list_files(album_path: str) -> list:
    """List files from topic_map for an album path."""
    album_path = safe_rel_path(album_path)
    key = normalize_storage_folder(album_path)
    mapping = load_topic_map()
    
    data = mapping.get(key) if isinstance(mapping, dict) else None
    if not isinstance(data, dict):
        return []
    
    msg_map = data.get("messages", {}) or {}
    out = []
    
    for fname in msg_map.keys():
        out.append({
            "name": fname,
            "path": f"{album_path.rstrip('/')}/{fname}",
            "type": "file",
            "icon": "fa-cloud",
            "meta": "CLOUD",
        })
    
    return out


# =============================================================================
# JOB QUEUE
# =============================================================================
jobs = {}
jobs_lock = threading.Lock()
folder_locks = {}
folder_locks_lock = threading.Lock()

executor = ThreadPoolExecutor(max_workers=4)


def get_folder_lock(rel_folder: str) -> threading.Lock:
    """Get or create a lock for a folder."""
    rel_folder = normalize_storage_folder(rel_folder)
    with folder_locks_lock:
        if rel_folder not in folder_locks:
            folder_locks[rel_folder] = threading.Lock()
        return folder_locks[rel_folder]


def job_update(job_id: str, **kwargs):
    """Update job status."""
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(kwargs)


# =============================================================================
# ASYNC DOWNLOAD ENGINE
# =============================================================================
def detect_platform(url: str) -> str:
    """Detect platform from URL."""
    url_lower = url.lower()
    
    if any(d in url_lower for d in ["tiktok.com", "vt.tiktok.com", "vm.tiktok.com"]):
        return "tiktok"
    if any(d in url_lower for d in ["twitter.com", "x.com", "t.co"]):
        return "twitter"
    if any(d in url_lower for d in ["instagram.com", "instagr.am"]):
        return "instagram"
    if any(d in url_lower for d in ["facebook.com", "fb.watch", "fb.com"]):
        return "facebook"
    
    return "universal"


async def run_download_async(url: str, platform: str) -> dict:
    """Run async download based on platform."""
    from plugins.tiktok import download_tiktok
    from plugins.twitter import download_twitter
    from plugins.instagram import download_instagram
    from plugins.facebook import download_facebook
    from plugins.universal import download_universal
    
    cookies_ig = str(COOKIES_INSTAGRAM) if COOKIES_INSTAGRAM.exists() else None
    cookies_tw = str(COOKIES_TWITTER) if COOKIES_TWITTER.exists() else None
    
    if platform == "tiktok":
        result = await download_tiktok(url)
    elif platform == "twitter":
        result = await download_twitter(url, cookies_file=cookies_tw)
    elif platform == "instagram":
        result = await download_instagram(url, cookies_file=cookies_ig)
    elif platform == "facebook":
        result = await download_facebook(url)
    else:
        result = await download_universal(url)
    
    return {
        "buffer": result.buffer,
        "filename": result.filename,
        "title": result.title,
        "description": result.description,
        "source_url": result.source_url,
        "source_username": result.source_username,
    }


def run_download_job(job_id: str, url: str, rel_folder: str, user: str):
    """Execute download job in thread pool."""
    rel_folder = normalize_storage_folder(rel_folder)
    lock = get_folder_lock(rel_folder)
    
    with lock:
        try:
            job_update(job_id, status="downloading", progress=0)
            
            # Detect platform
            platform = detect_platform(url)
            
            # Run async download
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(run_download_async(url, platform))
            finally:
                loop.close()
            
            job_update(job_id, status="uploading", file=result["filename"], progress=50)
            
            # Ensure topic exists
            topic_id = ensure_topic_for_folder(rel_folder)
            if not topic_id:
                raise DownloadError("Failed to create/find topic for folder")
            
            # Build caption
            desc = (result.get("description") or result.get("title") or "").strip()
            src_url = result.get("source_url") or url
            src_user = result.get("source_username") or ""
            
            MAX_DESC = 800
            if len(desc) > MAX_DESC:
                desc = desc[:MAX_DESC].rstrip() + "…"
            
            final_html = html.escape(result["filename"])
            desc_html = html.escape(desc) if desc else "—"
            src_url_html = html.escape(src_url)
            display_user = src_user if src_user.startswith("@") else f"@{src_user}" if src_user else "OPEN SOURCE"
            display_user_html = html.escape(display_user)
            
            caption_html = (
                f"▣ <b>ART'TERYX ARCHIVE</b>\n"
                f"⟦ <code>{final_html}</code> ⟧\n"
                f"━━━━━━━━━━━━━━\n"
                f"{desc_html}\n"
                f"━━━━━━━━━━━━━━\n"
                f"↳ <b>SOURCE</b>: <a href=\"{src_url_html}\">{display_user_html}</a>"
            )
            
            # Save buffer to temp file for upload (legacy method)
            import tempfile
            import shutil
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                result["buffer"].seek(0)
                tmp.write(result["buffer"].read())
                tmp_path = tmp.name
            
            try:
                # Upload using sync API (will be replaced with Pyrogram)
                import telebot
                bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
                
                with open(tmp_path, "rb") as f:
                    msg = bot.send_video(
                        chat_id=GROUP_ID,
                        video=f,
                        message_thread_id=topic_id,
                        caption=caption_html,
                        parse_mode="HTML",
                        supports_streaming=True,
                    )
                
                # Save to topic map
                with topic_lock:
                    mapping = load_topic_map()
                    mapping.setdefault(rel_folder, {"topic_id": topic_id, "messages": {}})
                    mapping[rel_folder].setdefault("messages", {})
                    mapping[rel_folder]["messages"][result["filename"]] = msg.message_id
                    save_topic_map(mapping)
                
                job_update(
                    job_id,
                    status="done",
                    progress=100,
                    message_id=msg.message_id,
                    file=result["filename"]
                )
                
            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        except Exception as e:
            app.logger.exception(f"Download job {job_id} failed")
            job_update(job_id, status="error", error=str(e))


# =============================================================================
# FLASK ROUTES
# =============================================================================
@app.get("/")
def index():
    """Main index route - file browser."""
    req_path = request.args.get("path", "")
    
    if req_path == "":
        auto_fix_structure()
    
    req_path = safe_rel_path(req_path)
    abs_path = safe_abs_from_rel(req_path) if req_path else BASE_DIR
    
    items = []
    if abs_path.exists():
        for entry in abs_path.iterdir():
            name = entry.name
            if name in BLOCKED_FILES or name.startswith("."):
                continue
            
            rel_item_path = str((Path(req_path) / name)).replace("\\", "/") if req_path else name
            is_dir = entry.is_dir()
            meta = "DIR" if is_dir else f"{round(entry.stat().st_size / 1024, 1)} KB"
            
            items.append({
                "name": name,
                "path": rel_item_path,
                "type": "folder" if is_dir else "file",
                "icon": "fa-folder" if is_dir else "fa-file-video",
                "meta": meta
            })
    
    # Breadcrumbs
    breadcrumbs = []
    acc = ""
    for part in req_path.split("/"):
        if part:
            acc = f"{acc}/{part}".strip("/")
            breadcrumbs.append({"name": part, "path": acc})
    
    # Downloader UI only in DOWNLOADER album
    is_album = is_album_level(req_path) and req_path.upper().startswith("DOWNLOADER")
    downloader_link = f"{WEB_APP_URL}?path={urllib.parse.quote(req_path)}&dl=1" if is_album else ""
    
    parts = req_path.split("/") if req_path else []
    
    # CLOUD INJECT: platform level -> albums
    if len(parts) == 3 and parts[1].upper() == "PLATFORM":
        virtual_albums = cloud_list_albums(req_path)
        existing = set([x["name"] for x in items if x["type"] == "folder"])
        for a in virtual_albums:
            if a["name"] not in existing:
                items.append(a)
    
    # CLOUD INJECT: album level -> files
    if is_album_level(req_path):
        virtual_files = cloud_list_files(req_path)
        existing_files = set([x["name"] for x in items if x["type"] == "file"])
        for f in virtual_files:
            if f["name"] not in existing_files:
                items.append(f)
    
    # Sort: folders first, then alphabetically
    items.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
    
    return render_template(
        "index.html",
        items=items,
        current_path=req_path,
        breadcrumbs=breadcrumbs,
        bot_username=BOT_USERNAME,
        is_album=is_album,
        downloader_link=downloader_link,
    )


@app.post("/create_folder")
def create_folder():
    """Create a new folder."""
    data = request.get_json(silent=True) or {}
    path = safe_rel_path(data.get("path", ""))
    name = (data.get("name") or "").strip()
    
    if not name:
        return jsonify({"success": False, "error": "Folder name required"}), 400
    
    # Validate path level
    up = path.upper()
    parts = path.split("/") if path else []
    
    allow = False
    if up == "DOWNLOADER/PLATFORM":
        allow = True
    elif len(parts) == 3 and parts[0].upper() == "DOWNLOADER" and parts[1].upper() == "PLATFORM":
        allow = True
    
    if not allow and path != "":
        return jsonify({
            "success": False,
            "error": "Folders can only be created in DOWNLOADER/PLATFORM or DOWNLOADER/PLATFORM/<platform>"
        }), 400
    
    try:
        target = safe_abs_from_rel(f"{path}/{name}".strip("/"))
        target.mkdir(parents=True, exist_ok=True)
        
        full_rel = normalize_storage_folder(str(Path(path) / name).replace("\\", "/"))
        if is_album_level(full_rel):
            topic_id = ensure_topic_for_folder(full_rel)
            if not topic_id:
                return jsonify({"success": False, "error": "Failed to create topic"}), 500
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/delete_item")
def delete_item():
    """Delete a file or folder."""
    data = request.get_json(silent=True) or {}
    rel_path = safe_rel_path(data.get("path", ""))
    
    if not rel_path:
        return jsonify({"success": False, "error": "Path required"}), 400
    
    try:
        import shutil
        
        mapping = load_topic_map()
        folder_rel = normalize_storage_folder(rel_path)
        
        # Delete album topic
        if folder_rel in mapping:
            t_id = mapping[folder_rel]["topic_id"]
            telegram_delete_topic(t_id)
            del mapping[folder_rel]
            save_topic_map(mapping)
        else:
            # Delete file message
            file_name = Path(rel_path).name
            parent_rel = normalize_storage_folder(str(Path(rel_path).parent).replace("\\", "/"))
            
            if parent_rel in mapping:
                msg_dict = mapping[parent_rel].get("messages", {}) or {}
                if file_name in msg_dict:
                    telegram_delete_message(msg_dict[file_name])
                    del mapping[parent_rel]["messages"][file_name]
                    save_topic_map(mapping)
        
        # Delete local paths
        abs_path = safe_abs_from_rel(rel_path)
        if abs_path.exists():
            if abs_path.is_dir():
                shutil.rmtree(abs_path, ignore_errors=True)
            else:
                abs_path.unlink(missing_ok=True)
        
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.get("/view/<path:filename>")
def view_file_route(filename):
    """Serve a local file."""
    rel = safe_rel_path(filename)
    abs_p = safe_abs_from_rel(rel)
    return send_file(abs_p)


@app.post("/api/download")
def api_download():
    """Start a download job."""
    data = request.get_json(silent=True) or {}
    url = (data.get("url") or "").strip()
    user = (data.get("user") or "Guest").strip()
    folder = safe_rel_path(data.get("folder", ""))
    
    try:
        url = sanitize_url(url)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    
    folder_norm = normalize_storage_folder(folder)
    
    if not is_album_level(folder_norm):
        return jsonify({
            "success": False,
            "error": "Downloads only allowed in album folders (DOWNLOADER/PLATFORM/<platform>/<album>)"
        }), 400
    
    job_id = uuid.uuid4().hex[:10]
    with jobs_lock:
        jobs[job_id] = {
            "status": "queued",
            "file": None,
            "error": None,
            "progress": 0,
        }
    
    executor.submit(run_download_job, job_id, url, folder_norm, user)
    return jsonify({"success": True, "job_id": job_id})


@app.get("/api/status/<job_id>")
def api_status(job_id):
    """Get download job status."""
    with jobs_lock:
        j = jobs.get(job_id)
        if not j:
            return jsonify({"success": False, "error": "Job not found"}), 404
        return jsonify({"success": True, **j})


# =============================================================================
# BOT HANDLERS (LEGACY - WILL BE MIGRATED TO PYROGRAM)
# =============================================================================
import telebot
from telebot import types

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
user_active_video = {}


def create_video_markup(rel_folder: str):
    """Create inline keyboard for video message."""
    rel_folder = normalize_storage_folder(rel_folder)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton(
        "🔙 BACK TO CATALOG",
        url=f"{WEB_APP_URL}?path={rel_folder}"
    ))
    markup.add(types.InlineKeyboardButton(
        "🗑️ CLOSE",
        callback_data="delete_video"
    ))
    return markup


@bot.message_handler(commands=["start"])
def handle_start(message):
    """Handle /start command."""
    if message.chat.type != "private":
        bot.reply_to(message, "Please open this bot in *Private Chat*.")
        return
    
    parts = message.text.split(maxsplit=1)
    start_param = parts[1].strip() if len(parts) > 1 else ""
    
    if not start_param:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(
            "🚀 ACCESS MAIN FRAME",
            web_app=types.WebAppInfo(url=WEB_APP_URL)
        ))
        bot.send_message(
            message.chat.id,
            "💀 *ART'TERYX SYSTEM CONNECTED*",
            reply_markup=markup
        )
        return
    
    if start_param.startswith("view_"):
        encoded_path = start_param.replace("view_", "", 1)
        target_rel = urllib.parse.unquote(encoded_path).replace("\\", "/")
        target_rel = safe_rel_path(target_rel)
        
        file_name = Path(target_rel).name
        parent_rel = str(Path(target_rel).parent).replace("\\", "/")
        parent_rel = normalize_storage_folder(parent_rel)
        
        mapping = load_topic_map()
        if parent_rel in mapping and file_name in (mapping[parent_rel].get("messages", {}) or {}):
            msg_id = mapping[parent_rel]["messages"][file_name]
            
            # Delete previous video if exists
            if message.chat.id in user_active_video:
                try:
                    bot.delete_message(message.chat.id, user_active_video[message.chat.id])
                except Exception:
                    pass
            
            sent = bot.copy_message(
                chat_id=message.chat.id,
                from_chat_id=GROUP_ID,
                message_id=msg_id,
                protect_content=True,
                reply_markup=create_video_markup(parent_rel),
            )
            user_active_video[message.chat.id] = sent.message_id
        else:
            bot.send_message(message.chat.id, "❌ *DATA NOT FOUND IN CLOUD*")
        return
    
    bot.send_message(message.chat.id, "Unknown start parameter.")


@bot.callback_query_handler(func=lambda call: call.data == "delete_video")
def callback_delete(call):
    """Handle delete video callback."""
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        if call.message.chat.id in user_active_video:
            del user_active_video[call.message.chat.id]
    except Exception:
        pass


# =============================================================================
# WEB APP DATA HANDLER (MINI APP INTEGRATION)
# =============================================================================
@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_data(message):
    """
    Handle data sent from the Telegram Mini App (Web App).
    
    Expected JSON format from Web App:
    {
        "action": "download",
        "url": "https://...",
        "folder": "DOWNLOADER/PLATFORM/TIKTOK/album_name",
        "user": "username"
    }
    """
    try:
        import json as json_lib
        
        # Parse the web_app_data
        data = json_lib.loads(message.web_app_data.data)
        action = data.get("action", "").lower()
        
        app.logger.info(f"Web App Data received: {action} from user {message.from_user.id}")
        
        if action == "download":
            # Extract download parameters
            url = (data.get("url") or "").strip()
            folder = safe_rel_path(data.get("folder", ""))
            user = data.get("user") or message.from_user.username or "Guest"
            
            # Validate URL
            try:
                url = sanitize_url(url)
            except ValueError as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ *Invalid URL*\n`{str(e)}`",
                    parse_mode="Markdown"
                )
                return
            
            # Validate folder
            folder_norm = normalize_storage_folder(folder)
            if not is_album_level(folder_norm):
                bot.send_message(
                    message.chat.id,
                    "❌ *Invalid folder*\nDownloads only allowed in album folders.",
                    parse_mode="Markdown"
                )
                return
            
            # Create job
            job_id = uuid.uuid4().hex[:10]
            with jobs_lock:
                jobs[job_id] = {
                    "status": "queued",
                    "file": None,
                    "error": None,
                    "progress": 0,
                    "chat_id": message.chat.id,
                }
            
            # Send initial status
            status_msg = bot.send_message(
                message.chat.id,
                f"⏳ *Download Started*\n"
                f"📁 Folder: `{folder_norm.split('/')[-1]}`\n"
                f"🔗 URL: `{url[:50]}...`\n"
                f"🆔 Job: `{job_id}`",
                parse_mode="Markdown"
            )
            
            # Store message ID for updates
            with jobs_lock:
                if job_id in jobs:
                    jobs[job_id]["status_message_id"] = status_msg.message_id
            
            # Submit download job
            executor.submit(
                run_download_job_with_notification,
                job_id, url, folder_norm, user, message.chat.id
            )
        
        elif action == "view":
            # Handle view file action
            target_path = safe_rel_path(data.get("path", ""))
            if target_path:
                file_name = Path(target_path).name
                parent_rel = str(Path(target_path).parent).replace("\\", "/")
                parent_rel = normalize_storage_folder(parent_rel)
                
                mapping = load_topic_map()
                if parent_rel in mapping and file_name in (mapping[parent_rel].get("messages", {}) or {}):
                    msg_id = mapping[parent_rel]["messages"][file_name]
                    
                    # Delete previous video if exists
                    if message.chat.id in user_active_video:
                        try:
                            bot.delete_message(message.chat.id, user_active_video[message.chat.id])
                        except Exception:
                            pass
                    
                    sent = bot.copy_message(
                        chat_id=message.chat.id,
                        from_chat_id=GROUP_ID,
                        message_id=msg_id,
                        protect_content=True,
                        reply_markup=create_video_markup(parent_rel),
                    )
                    user_active_video[message.chat.id] = sent.message_id
                else:
                    bot.send_message(message.chat.id, "❌ *File not found in cloud*", parse_mode="Markdown")
        
        elif action == "create_folder":
            # Handle folder creation
            path = safe_rel_path(data.get("path", ""))
            name = (data.get("name") or "").strip()
            
            if not name:
                bot.send_message(message.chat.id, "❌ *Folder name required*", parse_mode="Markdown")
                return
            
            try:
                full_rel = f"{path}/{name}".strip("/") if path else name
                target = safe_abs_from_rel(full_rel)
                target.mkdir(parents=True, exist_ok=True)
                
                full_rel_norm = normalize_storage_folder(full_rel.replace("\\", "/"))
                if is_album_level(full_rel_norm):
                    topic_id = ensure_topic_for_folder(full_rel_norm)
                    if topic_id:
                        bot.send_message(
                            message.chat.id,
                            f"✅ *Folder created*\n📁 `{name}`",
                            parse_mode="Markdown"
                        )
                    else:
                        bot.send_message(
                            message.chat.id,
                            "⚠️ *Folder created but topic creation failed*",
                            parse_mode="Markdown"
                        )
                else:
                    bot.send_message(
                        message.chat.id,
                        f"✅ *Folder created*\n📁 `{name}`",
                        parse_mode="Markdown"
                    )
            except Exception as e:
                bot.send_message(
                    message.chat.id,
                    f"❌ *Error creating folder*\n`{str(e)}`",
                    parse_mode="Markdown"
                )
        
        else:
            bot.send_message(
                message.chat.id,
                f"❓ *Unknown action*: `{action}`",
                parse_mode="Markdown"
            )
    
    except json_lib.JSONDecodeError:
        bot.send_message(
            message.chat.id,
            "❌ *Invalid data format from Web App*",
            parse_mode="Markdown"
        )
    except Exception as e:
        app.logger.exception("Web App Data handler error")
        bot.send_message(
            message.chat.id,
            f"❌ *Error processing request*\n`{str(e)}`",
            parse_mode="Markdown"
        )


def run_download_job_with_notification(job_id: str, url: str, rel_folder: str, user: str, chat_id: int):
    """
    Extended download job that sends Telegram notifications on progress.
    This is called from web_app_data handler.
    """
    rel_folder = normalize_storage_folder(rel_folder)
    lock = get_folder_lock(rel_folder)
    
    def send_update(text: str):
        """Send status update to user."""
        try:
            with jobs_lock:
                msg_id = jobs.get(job_id, {}).get("status_message_id")
            
            if msg_id:
                bot.edit_message_text(
                    text,
                    chat_id=chat_id,
                    message_id=msg_id,
                    parse_mode="Markdown"
                )
        except Exception:
            pass
    
    with lock:
        try:
            job_update(job_id, status="downloading", progress=0)
            send_update(f"⬇️ *Downloading...*\n🆔 Job: `{job_id}`")
            
            # Detect platform
            platform = detect_platform(url)
            
            # Run async download
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(run_download_async(url, platform))
            finally:
                loop.close()
            
            job_update(job_id, status="uploading", file=result["filename"], progress=50)
            send_update(f"⬆️ *Uploading to Telegram...*\n📄 `{result['filename']}`")
            
            # Ensure topic exists
            topic_id = ensure_topic_for_folder(rel_folder)
            if not topic_id:
                raise DownloadError("Failed to create/find topic for folder")
            
            # Build caption
            desc = (result.get("description") or result.get("title") or "").strip()
            src_url = result.get("source_url") or url
            src_user = result.get("source_username") or ""
            
            MAX_DESC = 800
            if len(desc) > MAX_DESC:
                desc = desc[:MAX_DESC].rstrip() + "…"
            
            final_html = html.escape(result["filename"])
            desc_html = html.escape(desc) if desc else "—"
            src_url_html = html.escape(src_url)
            display_user = src_user if src_user.startswith("@") else f"@{src_user}" if src_user else "OPEN SOURCE"
            display_user_html = html.escape(display_user)
            
            caption_html = (
                f"▣ <b>ART'TERYX ARCHIVE</b>\n"
                f"⟦ <code>{final_html}</code> ⟧\n"
                f"━━━━━━━━━━━━━━\n"
                f"{desc_html}\n"
                f"━━━━━━━━━━━━━━\n"
                f"↳ <b>SOURCE</b>: <a href=\"{src_url_html}\">{display_user_html}</a>"
            )
            
            # Save buffer to temp file for upload
            import tempfile
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
                result["buffer"].seek(0)
                tmp.write(result["buffer"].read())
                tmp_path = tmp.name
            
            try:
                # Upload to group
                with open(tmp_path, "rb") as f:
                    msg = bot.send_video(
                        chat_id=GROUP_ID,
                        video=f,
                        message_thread_id=topic_id,
                        caption=caption_html,
                        parse_mode="HTML",
                        supports_streaming=True,
                    )
                
                # Save to topic map
                with topic_lock:
                    mapping = load_topic_map()
                    mapping.setdefault(rel_folder, {"topic_id": topic_id, "messages": {}})
                    mapping[rel_folder].setdefault("messages", {})
                    mapping[rel_folder]["messages"][result["filename"]] = msg.message_id
                    save_topic_map(mapping)
                
                job_update(
                    job_id,
                    status="done",
                    progress=100,
                    message_id=msg.message_id,
                    file=result["filename"]
                )
                
                # Success notification
                send_update(
                    f"✅ *Download Complete!*\n"
                    f"📄 `{result['filename']}`\n"
                    f"☁️ Saved to Telegram Cloud"
                )
                
            finally:
                # Cleanup temp file
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
        
        except Exception as e:
            app.logger.exception(f"Download job {job_id} failed")
            job_update(job_id, status="error", error=str(e))
            send_update(f"❌ *Download Failed*\n`{str(e)}`")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    auto_fix_structure()
    
    print("🤖 Starting Telegram Bot polling...")
    bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
    bot_thread.start()
    
    print("🌐 Starting Flask server on port 5000...")
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
