import os
import requests
import asyncio
import re

async def download_tiktok(url, path):
    # Pastikan path folder tujuan sudah ada di sistem
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

    loop = asyncio.get_event_loop()
    try:
        video_info = await loop.run_in_executor(None, _download_process_tikwm, url, path)
        return video_info 
    except Exception as e:
        print(f"Error Tikwm: {e}")
        raise e

def _download_process_tikwm(url, path):
    api_url = "https://www.tikwm.com/api/"
    params = {"url": url, "hd": 1}
    
    res = requests.get(api_url, params=params).json()
    if res.get('code') != 0:
        raise Exception(f"Tikwm Error: {res.get('msg')}")
    
    data = res['data']
    video_url = data['hdplay'] if 'hdplay' in data else data['play']
    
    # 1. JUDUL: Bersihkan karakter agar aman di Linux/Windows
    title = data.get('title', 'Tiktok_Video')
    clean_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')[:50]
    if not clean_title: clean_title = data['id']
    
    # 2. FILE MANAGEMENT
    filename = f"{clean_title}.mp4"
    # SINKRONISASI: Menggabungkan path kiriman dashboard dengan nama file
    full_path = os.path.join(path, filename)
    
    # Download file secara sinkron di dalam executor
    video_data = requests.get(video_url).content
    with open(full_path, 'wb') as f:
        f.write(video_data)
        
    author = data.get("author") or {}
    source_username = None
    source_url = None

    if isinstance(author, dict):
        source_username = author.get("unique_id") or author.get("username") or author.get("name")
        source_url = author.get("url")

    if not source_url:
        source_url = url  # fallback minimal ke url video

    return {
        "path": full_path,
        "title": title,
        "description": title,   # TikTok caption
        "duration": data.get('duration', 0),
        "filename": filename,
        "source_url": source_url,
        "source_username": source_username,
    }

