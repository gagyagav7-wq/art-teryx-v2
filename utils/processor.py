import os
import subprocess
import json
import time
import shutil

def _probe_duration_sec(input_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        input_path
    ]
    try:
        out = subprocess.check_output(cmd).decode("utf-8", errors="ignore")
        data = json.loads(out)
        return float(data["format"]["duration"])
    except:
        return 0.0

def _check_gpu_available():
    """Cek apakah NVENC (Nvidia) tersedia biar gak error di VPS CPU Only"""
    try:
        subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.STDOUT)
        # Cara simpel: asumsikan kalau di Kaggle/PC Gaming pake nvenc, kalau VPS murah pake cpu
        # Kita try-catch di logic utama aja biar aman.
        return True
    except:
        return False

def process_video_hd_60fps(input_path: str, progress_cb=None):
    """
    UPGRADE: Smart High Quality Upscaler
    - Force 1080p (Resize with Lanczos for Sharpness)
    - Force 60fps
    - Sharpening Filter (Unsharp Mask)
    - Hybrid Encoder (NVENC/CPU Auto Switch)
    """

    if not os.path.exists(input_path):
        return None

    duration = _probe_duration_sec(input_path)
    if duration <= 0:
        duration = 1.0

    directory = os.path.dirname(input_path)
    filename = os.path.basename(input_path)
    output_filename = f"HD_1080_60_{filename}"
    output_path = os.path.join(directory, output_filename)

    # === FORMULA "TAJEM" (SHARP) ===
    # 1. scale: Resize ke 1080p pakai algoritma 'lanczos' (paling detail).
    # 2. pad: Biar aspect ratio gak gepeng (tetap proporsional, sisa hitam).
    # 3. unsharp: Filter penajam (luma_msize_x:luma_msize_y:luma_amount).
    #    3:3:1.5 artinya pertajam detail halus dengan kekuatan medium-strong.
    vf_filters = (
        "scale=1080:1920:force_original_aspect_ratio=decrease:flags=lanczos,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        "setsar=1,"
        "fps=60,"
        "unsharp=3:3:1.5:3:3:0.0" 
    )

    # Opsi Encoding Dasar
    base_cmd = [
        "ffmpeg", "-y", "-hide_banner",
        "-i", input_path,
        "-vf", vf_filters,
        "-c:a", "copy", # Audio copy aja biar jernih aslinya
        "-progress", "pipe:1", "-nostats"
    ]

    # Opsi Encoder: Coba NVENC (GPU) dulu, kalau gagal fallback ke CPU
    # Settingan ini dimaksimalkan untuk kualitas (High Bitrate)
    
    # Skenario 1: GPU (Ngebut & Bagus)
    cmd_gpu = base_cmd + [
        "-c:v", "h264_nvenc",
        "-preset", "p4", # Medium-Fast preset
        "-tune", "hq",
        "-rc", "vbr",
        "-cq", "20",     # Constant Quality (makin kecil makin bagus, 20 itu HD)
        "-maxrate", "10M",
        "-bufsize", "20M",
        output_path
    ]

    # Skenario 2: CPU (Kompatibel Semua VPS, agak lambat tapi kualitas Top)
    cmd_cpu = base_cmd + [
        "-c:v", "libx264",
        "-preset", "fast", # Biar gak kelamaan nunggu di VPS
        "-crf", "20",      # Quality visually lossless
        "-maxrate", "8M",
        "-bufsize", "16M",
        output_path
    ]

    print(f"🚀 PROCESS START: {filename} | Dur: {round(duration,1)}s")

    def run_ffmpeg(command_list):
        proc = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )

        last_emit = 0
        last_percent = -1
        speed = None

        for line in proc.stdout:
            line = (line or "").strip()
            if "=" not in line: continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()

            if k == "out_time_ms":
                try:
                    out_us = int(v)
                    percent = int(min(99, (out_us / (duration * 1_000_000)) * 100))
                except: percent = 0
                
                now = time.time()
                if percent != last_percent and (now - last_emit) > 0.5:
                    last_percent = percent
                    last_emit = now
                    if progress_cb: progress_cb(percent, speed)
            
            elif k == "speed": speed = v
            elif k == "progress" and v == "end":
                if progress_cb: progress_cb(100, speed)
        
        return proc.wait()

    # LOGIC EKSEKUSI: COBA GPU DULU, KALAU ERROR GANTI CPU
    try:
        # Coba pakai settingan GPU
        exit_code = run_ffmpeg(cmd_gpu)
        if exit_code != 0:
            raise RuntimeError("GPU Encoder failed, switching to CPU...")
    except Exception as e:
        print(f"⚠️ {e} -> Fallback to CPU Mode")
        # Hapus file corrupt hasil percobaan GPU (kalau ada)
        if os.path.exists(output_path): os.remove(output_path)
        # Jalankan settingan CPU
        try:
            exit_code = run_ffmpeg(cmd_cpu)
            if exit_code != 0:
                print("❌ CPU Process Failed also.")
                return None
        except:
            return None

    if os.path.exists(output_path):
        try:
            os.remove(input_path) # Hapus file asli
        except: pass
        print(f"✅ FINISHED UPGRADE: {output_filename}")
        return {"path": output_path, "filename": output_filename}
    
    return None
