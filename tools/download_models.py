"""
Project Chloe - Offline Neural Models Downloader
Resilient downloader with auto-resume and retry mechanism for Kokoro-82M ONNX models.
"""

import os
import sys
import time
import requests
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent.parent / "backend" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

def download_file_resilient(url: str, dest_path: Path, max_retries: int = 5):
    """Downloads large model files with automatic HTTP range resume and retry logic."""
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")
    
    for attempt in range(1, max_retries + 1):
        try:
            initial_pos = temp_path.stat().st_size if temp_path.exists() else 0
            headers = {"Range": f"bytes={initial_pos}-"} if initial_pos > 0 else {}
            
            with requests.get(url, headers=headers, stream=True, timeout=15) as r:
                if r.status_code in [200, 206]:
                    total_size = int(r.headers.get("content-length", 0)) + initial_pos
                    mode = "ab" if initial_pos > 0 else "wb"
                    
                    print(f"[*] Downloading {dest_path.name} (Attempt {attempt}/{max_retries})...")
                    with open(temp_path, mode) as f:
                        downloaded = initial_pos
                        for chunk in r.iter_content(chunk_size=1024 * 1024): # 1 MB chunks
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if total_size > 0:
                                    pct = min(100.0, (downloaded / total_size) * 100)
                                    sys.stdout.write(f"\r    -> {pct:.1f}% ({downloaded // (1024*1024)} MB / {total_size // (1024*1024)} MB)")
                                    sys.stdout.flush()

                    # Rename .part to final
                    if temp_path.exists():
                        temp_path.replace(dest_path)
                    print(f"\n[✓] Successfully downloaded {dest_path.name}")
                    return True
                elif r.status_code == 416: # Range not satisfiable (already completed)
                    if temp_path.exists():
                        temp_path.replace(dest_path)
                    return True
                else:
                    print(f"[!] Server returned HTTP {r.status_code}")
        except Exception as e:
            print(f"\n[!] Connection interrupted ({e}). Retrying in 3s...")
            time.sleep(3)

    return False

def main():
    print("=" * 60)
    print("PROJECT CHLOE // OFFLINE NEURAL MODELS SETUP")
    print("=" * 60)
    print(f"[*] Target Directory: {MODELS_DIR}")
    
    # Check Kokoro ONNX
    kokoro_path = MODELS_DIR / "kokoro-v1.0.onnx"
    if not kokoro_path.exists() or kokoro_path.stat().st_size < 1000000:
        download_file_resilient(KOKORO_MODEL_URL, kokoro_path)
    else:
        print(f"[+] Kokoro ONNX model already present ({round(kokoro_path.stat().st_size/(1024*1024), 1)} MB)")

    # Check Voices
    voices_path = MODELS_DIR / "voices-v1.0.bin"
    if not voices_path.exists() or voices_path.stat().st_size < 100000:
        download_file_resilient(KOKORO_VOICES_URL, voices_path)
    else:
        print(f"[+] Kokoro Voices file already present ({round(voices_path.stat().st_size/(1024*1024), 1)} MB)")

    print("\n[+] Setup check complete.")

if __name__ == "__main__":
    main()
