"""
Project Chloe - FastAPI High-Speed Gateway
Provides REST endpoints, WebSocket real-time audio/JSON streaming, split-path upload pipelines, and static UI mounting.
"""

import os
import socket
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from pydantic import BaseModel

from app.config import settings
from app.core.modes import OperatingMode, ModePolicy
from app.core.orchestrator import orchestrator
from app.audio.stt_engine import stt_engine
from app.audio.tts_engine import tts_engine
from app.pipeline.rag_ingestion import rag_pipeline
from app.pipeline.terabox_worker import terabox_worker
from app.mcp.dispatcher import mcp_dispatcher
from app.mcp.system_tools import SystemTools

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ChloeServer")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="Agentic Low-Latency Personal AI Assistant for Abhishek"
)

# CORS middleware for Flutter and remote web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static UI
STATIC_DIR = Path(__file__).parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the standalone futuristic Web HUD."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse("<h1>Project Chloe Gateway Active. Web HUD loading...</h1>")

@app.get("/api/status")
async def get_system_status():
    """Returns runtime health, active mode, and component readiness."""
    return {
        "status": "online",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "mode": settings.DEFAULT_MODE,
        "groq_configured": bool(settings.GROQ_API_KEY),
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "ollama_host": settings.OLLAMA_HOST,
        "chromadb_ready": bool(rag_pipeline.collection is not None),
        "platform": settings.BASE_STORAGE_DIR.as_posix()
    }

@app.get("/api/system/info")
async def get_telemetry():
    """Returns real-time hardware diagnostics."""
    return SystemTools.get_system_info()

@app.post("/api/system/unload_ollama")
async def unload_ollama_memory():
    """Instructs Ollama to drop idle models from RAM to free system memory."""
    await orchestrator.unload_ollama_models()
    return {"status": "success", "message": "Ollama resident models memory freed."}

@app.get("/api/network")
async def get_network_info():
    """Retrieves local LAN IP addresses for Android mobile pairing."""
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
    return {
        "hostname": socket.gethostname(),
        "local_ips": ips,
        "port": settings.PORT,
        "ws_url": f"ws://{ips[0] if ips else 'localhost'}:{settings.PORT}/ws/audio"
    }

@app.get("/api/tools")
async def list_tools():
    """Lists available MCP tools and their execution status."""
    return {
        "tools": list(mcp_dispatcher.tool_registry.keys()) + ["query_vault"],
        "modes": [m.value for m in OperatingMode]
    }

class ToolExecutionRequest(BaseModel):
    tool: str
    params: dict = {}
    mode: str = "PARTIALLY_ISOLATED"

class ApiKeyUpdateRequest(BaseModel):
    groq_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    ollama_host: Optional[str] = None

@app.get("/api/config/keys")
async def get_keys_status():
    return {
        "groq_configured": bool(settings.GROQ_API_KEY),
        "groq_preview": settings.GROQ_API_KEY[:8] + "..." if settings.GROQ_API_KEY else "",
        "groq_full": settings.GROQ_API_KEY or "",       # full value for auto-fill from .env
        "gemini_configured": bool(settings.GEMINI_API_KEY),
        "gemini_preview": settings.GEMINI_API_KEY[:8] + "..." if settings.GEMINI_API_KEY else "",
        "gemini_full": settings.GEMINI_API_KEY or "",   # full value for auto-fill from .env
        "ollama_host": settings.OLLAMA_HOST,
        "groq_model": settings.GROQ_LLM_MODEL,
        "gemini_model": settings.GEMINI_MODEL,
    }

@app.post("/api/config/keys")
async def update_keys(req: ApiKeyUpdateRequest):
    env_path = Path(__file__).resolve().parent.parent / ".env"
    env_content = ""
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            env_content = f.read()

    lines = env_content.splitlines()
    env_dict = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env_dict[k.strip()] = v.strip()

    if req.groq_api_key is not None:
        settings.GROQ_API_KEY = req.groq_api_key.strip()
        env_dict["GROQ_API_KEY"] = req.groq_api_key.strip()
    if req.gemini_api_key is not None:
        settings.GEMINI_API_KEY = req.gemini_api_key.strip()
        env_dict["GEMINI_API_KEY"] = req.gemini_api_key.strip()
    if req.ollama_host is not None:
        settings.OLLAMA_HOST = req.ollama_host.strip()
        env_dict["OLLAMA_HOST"] = req.ollama_host.strip()

    with open(env_path, "w", encoding="utf-8") as f:
        for k, v in env_dict.items():
            f.write(f"{k}={v}\n")

    orchestrator.reload_clients()
    return {"status": "success", "message": "API keys updated and activated successfully!"}

@app.post("/api/tool/execute")
async def direct_tool_execute(req: ToolExecutionRequest):
    """Direct REST invocation of an MCP tool."""
    mode = OperatingMode(req.mode) if req.mode in OperatingMode.__members__ else OperatingMode.PARTIALLY_ISOLATED
    result = await mcp_dispatcher.execute_tool(req.tool, req.params, mode)
    return result

@app.get("/api/vault/stats")
async def get_vault_statistics():
    """Returns live ChromaDB vector collection metrics, total chunks, and document inventory."""
    return rag_pipeline.get_vault_stats()

@app.get("/api/history")
async def get_conversation_history(limit: int = 40):
    """Returns persistent conversation history for Abhishek's active session."""
    from app.db.storage import db_storage
    messages = db_storage.get_recent_messages("session_abhishek", limit=limit)
    return {"status": "success", "messages": messages}

@app.delete("/api/vault/flush")
async def flush_vault_and_context():
    """Flushes all vector embeddings from ChromaDB and resets conversation context."""
    vault_res = rag_pipeline.flush_vault()
    # Also reset conversation messages in database
    try:
        from app.db.storage import db_storage
        db_storage.clear_all_history()
    except Exception as e:
        logger.warning(f"Failed to clear conversation history: {e}")
    return {
        "status": "success",
        "message": "ChromaDB vector vault and conversation context flushed cleanly.",
        "details": vault_res
    }

@app.delete("/api/vault/document/{filename:path}")
async def delete_vault_document(filename: str):
    """Deletes a specific document and its vector chunks from ChromaDB."""
    return rag_pipeline.delete_document(filename)

# =========================================================================
# Continuous Learning & Isolated Memory Management Endpoints
# =========================================================================

class AddMemoryRequest(BaseModel):
    category: str = "preference"
    memory_text: str
    confidence: float = 1.0

@app.get("/api/memory/list")
async def get_learned_memories_and_experiences(limit: int = 100):
    """Returns all learned user preferences, episodic memories, and cached task workflows."""
    from app.db.storage import db_storage
    from app.core.memory_engine import memory_engine
    
    memories = db_storage.get_all_user_memories(limit=limit)
    experiences = db_storage.get_task_experiences(limit=limit)
    stats = db_storage.get_learning_stats()
    
    return {
        "status": "success",
        "stats": stats,
        "memories": memories,
        "experiences": experiences
    }

@app.post("/api/memory/add")
async def add_learned_memory(req: AddMemoryRequest):
    """Explicitly teaches Chloe a new fact, preference, shortcut or instruction."""
    from app.core.memory_engine import memory_engine
    memory_id = memory_engine.record_memory(
        category=req.category,
        memory_text=req.memory_text,
        confidence=req.confidence,
        source_session="session_abhishek"
    )
    if memory_id:
        return {"status": "success", "message": "Memory learned and indexed successfully!", "memory_id": memory_id}
    raise HTTPException(status_code=400, detail="Failed to record memory.")

@app.delete("/api/memory/{memory_id}")
async def delete_learned_memory(memory_id: int):
    """Deletes an individual learned memory from SQLite and ChromaDB."""
    from app.db.storage import db_storage
    from app.core.memory_engine import memory_engine
    
    success = db_storage.delete_user_memory(memory_id)
    if memory_engine.memory_collection:
        try:
            memory_engine.memory_collection.delete(ids=[f"mem_{memory_id}"])
        except Exception:
            pass
            
    return {"status": "success" if success else "error", "message": f"Memory {memory_id} deleted."}

@app.get("/api/learning/stats")
async def get_continuous_learning_statistics():
    """Returns real-time learning metrics across all 3 tiers."""
    from app.db.storage import db_storage
    return {
        "status": "success",
        "stats": db_storage.get_learning_stats()
    }

@app.post("/api/learning/export")
async def export_training_dataset():
    """Exports curated conversation turns into JSONL format for local LoRA fine-tuning."""
    from app.core.memory_engine import memory_engine
    result = memory_engine.export_full_dataset()
    return result

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    mode: str = Form("PARTIALLY_ISOLATED")
):
    """
    Split-Path Ingestion:
    - Fast Path: Extracts text and indexes into ChromaDB vector vault.
    - Slow Path: Asynchronously offloads to cold storage / TeraBox vault.
    """
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 1. Fast Path: Document RAG indexing
    rag_result = await rag_pipeline.ingest_file(temp_path, file.filename)

    # 2. Slow Path: Cold storage vault worker in background
    asyncio.create_task(terabox_worker.offload_file(temp_path, file.filename))

    return {
        "status": "success",
        "filename": file.filename,
        "size_bytes": len(content),
        "fast_path": rag_result,
        "slow_path": "OFFLOAD_DISPATCHED"
    }

# Session state cache for mode & speech persistence
session_modes: Dict[str, OperatingMode] = {}
session_speaks: Dict[str, bool] = {}
session_voices: Dict[str, Optional[str]] = {}

async def check_and_start_ollama(websocket: WebSocket) -> bool:
    """Verifies if local Ollama server is running. If not, auto-starts it and waits 2s."""
    import socket
    import subprocess
    import os

    # 1. Quick loopback TCP check
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", 11434))
        s.close()
        return True # already online
    except Exception:
        pass

    # 2. Offline -> notify client and boot
    await websocket.send_json({
        "type": "model_info",
        "model": "Ollama Core Engine",
        "engine": "local",
        "mode": "STARTING..."
    })

    logger.info("Ollama is not running. Launching it automatically...")
    
    try:
        subprocess.Popen("start ollama", shell=True)
    except Exception:
        pass

    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            path = os.path.join(local_app_data, "Programs", "Ollama", "ollama app.exe")
            if os.path.exists(path):
                os.startfile(path)
    except Exception:
        pass

    # 3. Smart verification check loop (up to 10 seconds total, polling every 0.5s)
    for _ in range(20):
        await asyncio.sleep(0.5)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            s.connect(("127.0.0.1", 11434))
            s.close()
            logger.info("Ollama local server started successfully and verified.")
            return True
        except Exception:
            pass

    logger.warning("Auto-start command dispatched but could not verify Ollama connection within 10 seconds.")
    return False

@app.websocket("/ws/audio")
async def websocket_audio_endpoint(websocket: WebSocket):
    """
    Bidirectional Real-Time WebSocket Gateway:
    Handles voice PCM/WAV chunks or text prompts, streams tokens, dispatches MCP tools, and streams sentence audio frames.
    Supports asynchronous mid-request interruption/cancellation ("Stop button").
    """
    await websocket.accept()
    session_id = f"session_{id(websocket)}"
    logger.info(f"WebSocket client connected: {session_id}")
    session_modes[session_id] = OperatingMode.PARTIALLY_ISOLATED
    session_speaks[session_id] = True
    session_voices[session_id] = None

    active_task: Optional[asyncio.Task] = None

    async def handle_interaction(user_text, current_mode, speak_flag, voice_choice):
        nonlocal active_task
        try:
            async for event in orchestrator.process_interaction(session_id, user_text, current_mode, speak=speak_flag, voice=voice_choice):
                await websocket.send_json(event)
        except asyncio.CancelledError:
            logger.info(f"Interaction task for {session_id} was interrupted/cancelled.")
            await websocket.send_json({"type": "interrupted", "message": "Generation stopped."})
        except Exception as e:
            logger.error(f"Error in handle_interaction: {e}")

    try:
        while True:
            message = await websocket.receive()
            
            user_text = ""
            current_mode = session_modes.get(session_id, OperatingMode.PARTIALLY_ISOLATED)
            speak_flag = session_speaks.get(session_id, True)
            voice_choice = session_voices.get(session_id, None)

            # Handle Binary Audio Frame (Speech from mic)
            if "bytes" in message and message["bytes"]:
                # User started speaking -> cancel any running assistant responses (voice interrupt)
                if active_task and not active_task.done():
                    active_task.cancel()
                    active_task = None
                
                audio_bytes = message["bytes"]
                user_text = await stt_engine.transcribe_audio(audio_bytes)
                if user_text:
                    await websocket.send_json({
                        "type": "transcription",
                        "text": user_text
                    })
                else:
                    continue

            # Handle Text / JSON Frame
            elif "text" in message and message["text"]:
                try:
                    import json
                    payload = json.loads(message["text"])
                    
                    # Intercept STOP / INTERRUPT mid-request
                    if payload.get("type") == "stop":
                        logger.info(f"Stop command received for {session_id}")
                        if active_task and not active_task.done():
                            active_task.cancel()
                            active_task = None
                        continue
                        
                    user_text = payload.get("text", "")
                    mode_str = payload.get("mode", "PARTIALLY_ISOLATED")
                    speak_flag = payload.get("speak", True)
                    voice_override = payload.get("voice", None)
                    if voice_override:
                        voice_choice = voice_override
                        session_voices[session_id] = voice_choice

                    if mode_str in OperatingMode.__members__:
                        current_mode = OperatingMode(mode_str)
                        session_modes[session_id] = current_mode
                    session_speaks[session_id] = speak_flag
                except Exception:
                    user_text = message["text"]
                    speak_flag = True

            # If the user switched to FULLY_ISOLATED (Air-Gapped) mode, ensure Ollama is started!
            if current_mode == OperatingMode.FULLY_ISOLATED:
                await check_and_start_ollama(websocket)

            if not user_text.strip():
                continue

            # Cancel any existing active task before starting a new one
            if active_task and not active_task.done():
                active_task.cancel()

            active_task = asyncio.create_task(
                handle_interaction(user_text, current_mode, speak_flag, voice_choice)
            )

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {session_id}")
        if active_task and not active_task.done():
            active_task.cancel()
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if active_task and not active_task.done():
            active_task.cancel()
