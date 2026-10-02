"""
Project Chloe - End-to-End Live Integration Verification
Tests REST API, WebSocket streaming, MCP tool execution, and Document RAG.
"""

import sys
import asyncio
import json
import aiohttp
import websockets
from pathlib import Path

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/audio"

async def test_rest_endpoints():
    print("\n--- 1. Testing REST Endpoints ---")
    async with aiohttp.ClientSession() as session:
        # Status
        async with session.get(f"{BASE_URL}/api/status") as resp:
            assert resp.status == 200, f"Status check failed: {resp.status}"
            data = await resp.json()
            print(f"[+] /api/status -> App: {data.get('app')}, Version: {data.get('version')}")

        # System Info
        async with session.get(f"{BASE_URL}/api/system/info") as resp:
            assert resp.status == 200, "System info failed"
            data = await resp.json()
            print(f"[+] /api/system/info -> CPU: {data.get('cpu', {}).get('percent')}%, RAM: {data.get('memory', {}).get('used_percent')}%")

        # Network
        async with session.get(f"{BASE_URL}/api/network") as resp:
            assert resp.status == 200, "Network check failed"
            data = await resp.json()
            print(f"[+] /api/network -> Local IPs: {data.get('local_ips')}")

        # Config Keys
        async with session.get(f"{BASE_URL}/api/config/keys") as resp:
            assert resp.status == 200, "Config keys check failed"
            data = await resp.json()
            print(f"[+] /api/config/keys -> Groq Configured: {data.get('groq_configured')}, Gemini Configured: {data.get('gemini_configured')}")

    print("[OK] REST Endpoints verified successfully.")

async def test_document_upload():
    print("\n--- 2. Testing Document Upload & RAG Ingestion ---")
    async with aiohttp.ClientSession() as session:
        test_file_content = b"Project Chloe 2.0 is Abhishek's personal AI assistant. It operates under a 6.5 GB active RAM limit on an Intel i5 13th Gen laptop."
        data = aiohttp.FormData()
        data.add_field('file', test_file_content, filename='live_test_manual.txt', content_type='text/plain')
        data.add_field('mode', 'PARTIALLY_ISOLATED')

        async with session.post(f"{BASE_URL}/api/upload", data=data) as resp:
            assert resp.status == 200, f"Upload failed: {resp.status}"
            res = await resp.json()
            print(f"[+] /api/upload -> Status: {res.get('status')}, File: {res.get('filename')}, FastPath: {res.get('fast_path', {}).get('status')}")
            assert res.get("status") == "success"

    print("[OK] Document Upload & RAG Ingestion verified successfully.")

async def test_websocket_stream():
    print("\n--- 3. Testing WebSocket Real-Time Conversation Stream ---")
    async with websockets.connect(WS_URL) as ws:
        # Send greeting
        await ws.send(json.dumps({"text": "Hello Chloe, state your active mode", "mode": "FULLY_ISOLATED", "speak": False}))
        
        tokens_received = []
        audio_chunks = 0
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=30.0)
                data = json.loads(msg)
                event_type = data.get("type")
                
                if event_type == "token":
                    tokens_received.append(data.get("token", ""))
                elif event_type == "sentence_audio":
                    audio_chunks += 1
                elif event_type == "done":
                    break
            except asyncio.TimeoutError:
                print("[!] Timeout waiting for next WebSocket frame")
                break

        full_text = "".join(tokens_received)
        print(f"[+] WebSocket Stream completed -> Tokens: {len(tokens_received)}, Audio Frames: {audio_chunks}")
        print(f"[+] Response sample: '{full_text[:120]}...'")
        assert len(tokens_received) > 0, "No tokens received from WebSocket!"

    print("[OK] WebSocket Real-Time Conversation Stream verified successfully.")

async def test_fast_path_command():
    print("\n--- 4. Testing Zero-Latency Command Interceptor ('open cmd') ---")
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"text": "Chloe open cmd", "mode": "PARTIALLY_ISOLATED", "speak": False}))
        
        events = []
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                events.append(data.get("type"))
                if data.get("type") == "tool_start":
                    print(f"[+] Fast-Path Intercepted: tool={data.get('tool')}, params={data.get('params')}")
                elif data.get("type") == "tool_result":
                    print(f"[+] Fast-Path Executed: status={data.get('result', {}).get('status')}")
                elif data.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                break

        assert "tool_start" in events, "Fast-path command was not intercepted!"
        assert "tool_result" in events, "Fast-path tool was not executed!"
        print("[OK] Zero-Latency Command Interception & Execution verified successfully.")

async def test_fast_path_website():
    print("\n--- 5. Testing Zero-Latency Website Interceptor ('open github.com') ---")
    async with websockets.connect(WS_URL) as ws:
        await ws.send(json.dumps({"text": "open github.com", "mode": "COMPLETELY_OPEN", "speak": False}))
        
        events = []
        tool_res = None
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=10.0)
                data = json.loads(msg)
                events.append(data.get("type"))
                if data.get("type") == "tool_start":
                    print(f"[+] Fast-Path Intercepted Website: tool={data.get('tool')}, params={data.get('params')}")
                elif data.get("type") == "tool_result":
                    tool_res = data.get("result", {})
                    print(f"[+] Fast-Path Executed: status={tool_res.get('status')}, message={tool_res.get('message')}")
                elif data.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                break

        assert "tool_start" in events, "Website command was not intercepted!"
        assert "tool_result" in events, "Website tool was not executed!"
        assert tool_res.get("status") == "success", "Website opening failed!"
        print("[OK] Zero-Latency Website Interception ('open github.com') verified successfully.")

async def main():
    print("=" * 60)
    print("PROJECT CHLOE 2.0 // LIVE INTEGRATION VERIFICATION")
    print("=" * 60)
    await test_rest_endpoints()
    await test_document_upload()
    await test_websocket_stream()
    await test_fast_path_command()
    await test_fast_path_website()
    print("\n" + "=" * 60)
    print("ALL PROJECT CHLOE 2.0 LIVE SUBSYSTEMS VERIFIED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
