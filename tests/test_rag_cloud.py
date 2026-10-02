import asyncio
import json
import aiohttp
import websockets

BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/audio"

async def test_chromadb_ingest():
    print("\n--- 1. Ingesting Unique Knowledge into ChromaDB ---")
    unique_content = b"SECRET PROJECT CODENAME: APOLLO-99. The designated recovery frequency is 142.850 MHz."
    
    async with aiohttp.ClientSession() as session:
        data = aiohttp.FormData()
        data.add_field('file', unique_content, filename='apollo_spec.txt', content_type='text/plain')
        data.add_field('mode', 'COMPLETELY_OPEN')

        async with session.post(f"{BASE_URL}/api/upload", data=data) as resp:
            assert resp.status == 200
            res = await resp.json()
            print(f"[+] Ingestion status: {res.get('status')}, Chunks: {res.get('chunks_indexed')}")
            assert res.get("status") == "success"

async def test_frontier_cloud_rag_retrieval():
    print("\n--- 2. Testing Frontier Cloud (Gemini) RAG Context Retrieval ---")
    async with websockets.connect(WS_URL) as ws:
        query = "What is the designated recovery frequency for Apollo-99?"
        await ws.send(json.dumps({"text": query, "mode": "COMPLETELY_OPEN", "speak": False}))
        
        tokens = []
        model_info = None
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=12.0)
                data = json.loads(msg)
                if data.get("type") == "token":
                    tokens.append(data.get("token", ""))
                elif data.get("type") == "model_info":
                    model_info = data
                elif data.get("type") == "done":
                    break
            except asyncio.TimeoutError:
                break

        full_reply = "".join(tokens)
        print(f"[+] Executing Model: {model_info.get('model')} ({model_info.get('engine')})")
        print(f"[+] Reply from Gemini with ChromaDB context:\n    '{full_reply.strip()}'")
        
        # Verify accurate fact extraction from ChromaDB
        assert "142.850" in full_reply or "142" in full_reply, "ChromaDB context was NOT retrieved by Gemini Cloud model!"
        print("[OK] Frontier Cloud RAG Context Retrieval Test PASSED!")

async def test_ollama_unload():
    print("\n--- 3. Testing Ollama RAM Memory Drop ---")
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{BASE_URL}/api/system/unload_ollama") as resp:
            assert resp.status == 200
            data = await resp.json()
            print(f"[+] Unload API status: {data.get('status')}")
            assert data.get("status") == "success"
    print("[OK] Ollama RAM Unload Test PASSED!")

async def main():
    print("=" * 60)
    print("PROJECT CHLOE 2.0 // CLOUD RAG & RAM RECOVERY VERIFICATION")
    print("=" * 60)
    await test_chromadb_ingest()
    await test_frontier_cloud_rag_retrieval()
    await test_ollama_unload()
    print("\n" + "=" * 60)
    print("ALL CLOUD RAG CONTEXT & RAM TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
