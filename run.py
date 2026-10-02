"""
Project Chloe - Launcher & Health Verification Script
Starts FastAPI gateway on 0.0.0.0:8000 and validates system components.
"""

import os
import sys
from pathlib import Path
import uvicorn

# Handle both frozen PyInstaller package and standard directory execution
if getattr(sys, "frozen", False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    BASE_DIR = Path(sys.executable).resolve().parent
    BACKEND_DIR = BUNDLE_DIR
    sys.path.insert(0, str(BUNDLE_DIR))
else:
    BASE_DIR = Path(__file__).resolve().parent
    BACKEND_DIR = BASE_DIR / "backend"
    sys.path.insert(0, str(BACKEND_DIR))

def main():
    print("=" * 60, flush=True)
    print("PROJECT CHLOE 2.0 // ABHISHEK'S PERSONAL AGENTIC AI", flush=True)
    print("=" * 60, flush=True)
    print(f"[*] Base Directory: {BASE_DIR}", flush=True)
    print(f"[*] Backend Directory: {BACKEND_DIR}", flush=True)
    
    # Check dependencies
    try:
        import fastapi
        import uvicorn
        import edge_tts
        print("[+] Core server dependencies verified.", flush=True)
    except ImportError as e:
        print(f"[!] Warning: Missing dependency: {e}", flush=True)
        print("[*] Run: pip install -r backend/requirements.txt", flush=True)

    print("[*] Starting FastAPI Gateway at http://0.0.0.0:8000", flush=True)
    print("[*] Web HUD available at: http://localhost:8000", flush=True)
    print("[*] WebSocket Stream at: ws://localhost:8000/ws/audio", flush=True)
    print("=" * 60, flush=True)

    from app.main import app
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()
