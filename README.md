# 🎯 ART'TERYX - God-Tier Media Downloader

> **Aria2-class Telegram Media Archiver with Zero-Disk Streaming**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Transform your Telegram into **unlimited cloud storage** for media with IDM-style download speeds.

---

## ⚡ Features

| Feature | Description |
|---------|-------------|
| **🚀 Multi-Connection Downloads** | Aria2-style parallel chunk fetching (up to 16 connections) |
| **☁️ Zero-Disk Streaming** | Direct memory buffer → Telegram Cloud (no VPS disk usage) |
| **🔍 Universal Sniffer** | Auto-detects media from ANY direct URL |
| **📱 Platform Handlers** | Optimized for TikTok, Twitter/X, Instagram, Facebook |
| **📁 Cloud File Manager** | Web UI for browsing your Telegram-stored media |
| **🔐 Secure** | All credentials in `.env`, input sanitization, path traversal protection |

---

## 🏗️ Architecture

### Zero-Disk Streaming Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ZERO-DISK ARCHITECTURE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  SOURCE URL ──┬──▶ [CHUNK 1] ──┐                               │
│               ├──▶ [CHUNK 2] ──┤                               │
│               ├──▶ [CHUNK 3] ──┼──▶ BytesIO Buffer ──▶ Telegram│
│               ├──▶ [CHUNK 4] ──┤     (RAM only)                │
│               └──▶ [CHUNK N] ──┘                               │
│                                                                 │
│  ❌ NO DISK WRITE at any point                                 │
│  ✅ Direct memory → Telegram Cloud                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Component Architecture

```
art-teryx/
├── app.py                 # Main Flask + Bot application
├── requirements.txt       # Python dependencies
├── .env.example          # Environment template
│
├── core/                  # High-Performance Engine
│   ├── __init__.py
│   ├── downloader.py     # Aria2-style multi-connection downloader
│   ├── streamer.py       # Pyrogram zero-disk uploader
│   └── sniffer.py        # Universal URL detector
│
├── plugins/               # Platform Handlers
│   ├── __init__.py
│   ├── tiktok.py         # TikTok (TikWM API)
│   ├── twitter.py        # Twitter/X (yt-dlp)
│   ├── instagram.py      # Instagram (yt-dlp + cookies)
│   ├── facebook.py       # Facebook (yt-dlp)
│   └── universal.py      # IDM-style direct downloads
│
├── templates/             # Web UI
│   └── index.html
│
└── DOWNLOADER/            # Virtual folder structure
    └── PLATFORM/
        ├── TIKTOK/
        ├── INSTAGRAM/
        ├── TWITTER/
        ├── FACEBOOK/
        └── UNIVERSAL/
```

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/art-teryx.git
cd art-teryx

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Telegram Bot (from @BotFather)
BOT_TOKEN=your_bot_token_here
BOT_USERNAME=your_bot_username

# Telegram API (from https://my.telegram.org)
API_ID=your_api_id
API_HASH=your_api_hash

# Target Group (must have Topics enabled)
GROUP_ID=-100xxxxxxxxxx

# Your deployed URL
WEB_APP_URL=https://your-domain.com

# Optional
ADMIN_IDS=123456789
SECRET_KEY=random_secret_string
```

### 3. Get Telegram API Credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Click "API development tools"
4. Create a new application
5. Copy `api_id` and `api_hash` to your `.env`

### 4. Setup Target Group

1. Create a Telegram **Supergroup**
2. Enable **Topics** in group settings
3. Add your bot as **Admin** with these permissions:
   - Delete messages
   - Manage topics
   - Post messages
4. Get the group ID (starts with `-100`)

### 5. Run

```bash
python app.py
```

The bot will start polling and the web UI will be available at `http://localhost:5000`

---

## 📖 Usage

### Web Interface

1. Open the Web App URL in your browser
2. Navigate to `DOWNLOADER/PLATFORM/<platform>/<album>`
3. Paste a media URL and click download
4. Video is streamed directly to Telegram Cloud

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Open the main menu with Web App button |
| `/start view_<path>` | View a specific file from cloud storage |

### Supported Platforms

| Platform | URL Examples | Cookie Required |
|----------|--------------|-----------------|
| **TikTok** | `https://vt.tiktok.com/xxx`, `https://tiktok.com/@user/video/xxx` | ❌ |
| **Twitter/X** | `https://x.com/user/status/xxx`, `https://twitter.com/...` | ⚠️ Recommended |
| **Instagram** | `https://instagram.com/reel/xxx`, `https://instagram.com/p/xxx` | ✅ Required |
| **Facebook** | `https://fb.watch/xxx`, `https://facebook.com/.../videos/xxx` | ⚠️ For private |
| **Universal** | Any direct `.mp4`, `.mkv`, `.webm` URL | ❌ |

### Adding Cookies (for Instagram/Twitter)

1. Install a browser extension like "Get cookies.txt"
2. Log into the platform and export cookies
3. Save as `cookies_instagram.txt` or `cookies_x.txt` in the project root

---

## 🔧 How Zero-Disk Streaming Works

### Traditional Approach (Disk-Heavy)
```
URL → Download to disk → Read from disk → Upload to Telegram → Delete file
      ^^^^^^^^^^^^^^^^                     ^^^^^^^^^^^^^^^
      DISK WRITE                           DISK READ
```

### ART'TERYX Approach (Zero-Disk)
```
URL → Multi-connection chunks → BytesIO buffer → Telegram upload
      ^^^^^^^^^^^^^^^^^^^^      ^^^^^^^^^^^^^
      PARALLEL DOWNLOAD         MEMORY ONLY
```

**Key Components:**

1. **`core/downloader.py`** - Fetches file in parallel chunks (like Aria2's `-x16`)
2. **`core/sniffer.py`** - Detects if URL is direct media or needs extraction
3. **`core/streamer.py`** - Uploads BytesIO directly to Telegram via Pyrogram

**Memory Management:**
- Telegram limit: 2GB per file
- Recommended VPS RAM: 2GB+ for large files
- Buffer is released immediately after upload

---

## 🗂️ Folder Structure Explained

```
DOWNLOADER/
└── PLATFORM/
    ├── TIKTOK/
    │   ├── dance_videos/     ← Album (creates Telegram Topic)
    │   └── memes/            ← Album
    ├── INSTAGRAM/
    │   └── reels_2024/       ← Album
    └── UNIVERSAL/
        └── misc_downloads/   ← Album
```

- **DOWNLOADER** - Root folder for downloads
- **PLATFORM** - Contains platform-specific subfolders
- **Album** - Each album creates a **Forum Topic** in your Telegram group
  - Files are stored in Telegram, not on disk
  - The `topic_map.json` tracks which messages belong to which album

---

## 🛡️ Security Features

| Feature | Implementation |
|---------|----------------|
| **No hardcoded credentials** | All secrets in `.env` |
| **URL sanitization** | Blocks `javascript:`, `data:`, `file:` protocols |
| **Path traversal protection** | Blocks `..` in paths |
| **Admin whitelist** | Optional `ADMIN_IDS` for restricted access |
| **Protected content** | Videos sent with `protect_content=True` |

---

## 🚧 Troubleshooting

### "Topic creation failed"
- Ensure bot is **Admin** in the group
- Ensure group has **Topics enabled**
- Check `GROUP_ID` starts with `-100`

### "API_ID or API_HASH missing"
- Get credentials from [my.telegram.org](https://my.telegram.org)
- Ensure no spaces in `.env` values

### Instagram/Twitter downloads fail
- Add cookies file (see "Adding Cookies" section)
- Cookies expire - refresh if downloads start failing

### Out of memory on large files
- Increase VPS RAM or use swap
- Consider processing in chunks for files >1GB

---

## 📄 License

MIT License - feel free to modify and distribute.

---

## 🙏 Credits

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - Media extraction
- [Pyrogram](https://github.com/pyrogram/pyrogram) - Async Telegram client
- [TikWM](https://tikwm.com) - TikTok API
- [aiohttp](https://github.com/aio-libs/aiohttp) - Async HTTP

---

**Built with 💀 by ART'TERYX**