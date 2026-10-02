"""
Project Chloe - Configuration Module
Manages application settings, environment variables, model routing, and storage paths.
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file with support for frozen PyInstaller environment
if getattr(sys, "frozen", False):
    EXE_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(sys._MEIPASS)
    BACKEND_DIR = BUNDLE_DIR
    env_file = EXE_DIR / ".env" if (EXE_DIR / ".env").exists() else BUNDLE_DIR / ".env"
    DATA_DEFAULT = EXE_DIR / "data"
else:
    EXE_DIR = Path(__file__).resolve().parent.parent.parent
    BACKEND_DIR = Path(__file__).resolve().parent.parent
    env_file = BACKEND_DIR / ".env" if (BACKEND_DIR / ".env").exists() else EXE_DIR / ".env"
    DATA_DEFAULT = BACKEND_DIR / "data"

load_dotenv(env_file)

class Settings:
    # App Info
    APP_NAME: str = "Project Chloe"
    VERSION: str = "2.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")
    
    # Server Binding
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # AI API Keys
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Cyber Intelligence API Keys
    NVD_API_KEY: str = os.getenv("NVD_API_KEY", "")
    ABUSEIPDB_API_KEY: str = os.getenv("ABUSEIPDB_API_KEY", "")
    VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY", "")
    
    # Ollama Local Service & Specialized Qwen Models
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "chloe:latest")               # Primary voice & MCP dispatching
    OLLAMA_MODEL_CODER: str = os.getenv("OLLAMA_MODEL_CODER", "qwen2.5-coder:7b") # Code analysis & security audit
    OLLAMA_MODEL_VISION: str = os.getenv("OLLAMA_MODEL_VISION", "qwen2.5vl:3b")  # OCR, scanned PDFs, screenshots & diagrams
    OLLAMA_MODEL_OFFLINE: str = os.getenv("OLLAMA_MODEL_OFFLINE", "qwen3:0.6b")  # Lightweight offline standby engine
    
    # Model Selections
    GROQ_LLM_MODEL: str = os.getenv("GROQ_LLM_MODEL", "qwen/qwen3.8-27b")
    GROQ_FAST_MODEL: str = os.getenv("GROQ_FAST_MODEL", "openai/gpt-oss-20b")
    GROQ_WHISPER_MODEL: str = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    
    # Audio & TTS Settings
    DEFAULT_TTS_VOICE: str = os.getenv("DEFAULT_TTS_VOICE", "en-US-AriaNeural")
    TTS_FALLBACK_VOICE: str = os.getenv("TTS_FALLBACK_VOICE", "en-GB-SoniaNeural")
    TTS_RATE: str = os.getenv("TTS_RATE", "+15%")
    TTS_PITCH: str = os.getenv("TTS_PITCH", "+0Hz")
    KOKORO_ONNX_PATH: str = os.getenv("KOKORO_ONNX_PATH", str(BACKEND_DIR / "models" / "kokoro-v1.0.onnx") if (BACKEND_DIR / "models" / "kokoro-v1.0.onnx").exists() else str(EXE_DIR / "backend" / "models" / "kokoro-v1.0.onnx"))
    KOKORO_VOICES_PATH: str = os.getenv("KOKORO_VOICES_PATH", str(BACKEND_DIR / "models" / "voices-v1.0.bin") if (BACKEND_DIR / "models" / "voices-v1.0.bin").exists() else str(EXE_DIR / "backend" / "models" / "voices-v1.0.bin"))
    
    # Storage & Persistence Paths
    BASE_STORAGE_DIR: Path = Path(os.getenv("CHLOE_DATA_DIR", str(DATA_DEFAULT)))
    CHROMA_PERSIST_DIR: str = str(BASE_STORAGE_DIR / "chroma_db")           # General Document Vault
    MEMORY_CHROMA_DIR: str = str(BASE_STORAGE_DIR / "memory_chroma_db")     # Isolated Continuous Learning Database
    VAULT_DIR: str = str(BASE_STORAGE_DIR / "vault")
    LOGS_DIR: str = str(BASE_STORAGE_DIR / "logs")
    DATASET_DIR: str = str(BASE_STORAGE_DIR / "training_datasets")
    TRAIN_JSONL_PATH: str = str(BASE_STORAGE_DIR / "training_datasets" / "chloe_train.jsonl")
    DB_PATH: str = str(BASE_STORAGE_DIR / "chloe.db")
    
    # Redis & Database Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    POSTGRES_URL: str = os.getenv("POSTGRES_URL", "")
    
    # Operating Mode default: PARTIALLY_ISOLATED (Fast Hybrid Local)
    DEFAULT_MODE: str = os.getenv("DEFAULT_MODE", "PARTIALLY_ISOLATED")

settings = Settings()

# Ensure critical data directories exist
os.makedirs(settings.BASE_STORAGE_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
os.makedirs(settings.MEMORY_CHROMA_DIR, exist_ok=True)
os.makedirs(settings.VAULT_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)
os.makedirs(settings.DATASET_DIR, exist_ok=True)
