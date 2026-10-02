import os
import sys
import time
import requests
from pathlib import Path

MODELS_DIR = Path(r"D:\Chloe\backend\models")
MODELS_DIR.mkdir(parents=True, exist_ok=True)

KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

def download_file(url: str, dest: Path):
    temp = dest.with_suffix(".download")
    initial_pos = temp.stat().st_size if temp.exists() else 0
    headers = {"Range": f"bytes={initial_pos}-"} if initial_pos > 0 else {}
    
    print(f"[*] Downloading {dest.name} from {url}...")
    for attempt in range(1, 10):
        try:
            with requests.get(url, headers=headers, stream=True, timeout=20) as r:
                if r.status_code in [200, 206]:
                    total = int(r.headers.get("content-length", 0)) + initial_pos
                    mode = "ab" if initial_pos > 0 else "wb"
                    with open(temp, mode) as f:
                        cur = initial_pos
                        for chunk in r.iter_content(chunk_size=512*1024):
                            if chunk:
                                f.write(chunk)
                                cur += len(chunk)
                                if total > 0:
                                    pct = min(100.0, (cur / total) * 100)
                                    sys.stdout.write(f"\r  [{dest.name}] {pct:.1f}% ({cur//(1024*1024)}MB / {total//(1024*1024)}MB)")
                                    sys.stdout.flush()
                    if temp.exists():
                        if dest.exists():
                            dest.unlink()
                        temp.replace(dest)
                    print(f"\n[+] {dest.name} complete!")
                    return True
                elif r.status_code == 416: # already full
                    if temp.exists():
                        if dest.exists():
                            dest.unlink()
                        temp.replace(dest)
                    print(f"\n[+] {dest.name} already complete!")
                    return True
        except Exception as e:
            print(f"\n[!] Connection dropped ({e}), retrying in 2s...")
            time.sleep(2)
            initial_pos = temp.stat().st_size if temp.exists() else 0
            headers = {"Range": f"bytes={initial_pos}-"} if initial_pos > 0 else {}
    return False

if __name__ == "__main__":
    download_file(VOICES_URL, MODELS_DIR / "voices-v1.0.bin")
    download_file(KOKORO_URL, MODELS_DIR / "kokoro-v1.0.onnx")
