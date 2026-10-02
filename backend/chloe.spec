# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

datas = [
    ('app/static', 'app/static'),
    ('models/kokoro-v1.0.onnx', 'models'),
    ('models/voices-v1.0.bin', 'models'),
]

datas += collect_data_files('chromadb')
datas += collect_data_files('onnxruntime')

hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'fastapi.staticfiles',
    'pydantic',
    'pydantic_core',
    'pydantic_settings',
    'chromadb',
    'onnxruntime',
    'kokoro_onnx',
    'soundfile',
    'scipy',
    'numpy',
    'aiohttp',
    'requests',
    'groq',
    'google.genai',
    'langgraph',
    'langgraph.graph',
    'app.core.orchestrator',
    'app.core.langgraph_router',
    'app.core.memory_engine',
    'app.core.nlp_engine',
    'app.mcp.dispatcher',
    'app.mcp.system_tools',
    'app.mcp.cyber_tools',
    'app.pipeline.rag_ingestion',
    'app.pipeline.terabox_worker',
    'app.audio.stt_engine',
    'app.audio.tts_engine',
    'app.audio.stream_buffer',
    'app.db.storage'
]

hiddenimports += collect_submodules('chromadb')
hiddenimports += collect_submodules('uvicorn')

a = Analysis(
    ['../run.py'],
    pathex=['.', 'd:/Chloe/backend', 'd:/Chloe'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['PyQt6', 'matplotlib', 'IPython', 'torch', 'torchvision', 'torchaudio', 'notebook', 'nbconvert'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Chloe',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app/static/favicon.ico' if os.path.exists('app/static/favicon.ico') else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Chloe',
)
