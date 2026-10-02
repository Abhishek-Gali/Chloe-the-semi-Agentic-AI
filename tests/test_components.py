"""
Project Chloe - Comprehensive Component Verification Test Suite
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

async def test_stream_buffer():
    print("\n--- 1. Testing SentenceStreamBuffer ---")
    from app.audio.stream_buffer import SentenceStreamBuffer
    
    sentences_received = []
    def on_sentence(s):
        sentences_received.append(s)

    buffer = SentenceStreamBuffer(on_sentence_ready=on_sentence)
    
    tokens = ["Hello ", "Abhishek. ", "I have ", "analyzed the ", "network status. ", "All systems ", "are optimal!"]
    for t in tokens:
        async for s in buffer.process_token(t):
            pass
    async for s in buffer.flush():
        pass
        
    print(f"Sentences parsed ({len(sentences_received)}): {sentences_received}")
    assert len(sentences_received) >= 2, "Stream buffer failed to chunk sentences!"
    print("[OK] SentenceStreamBuffer test PASSED.")

async def test_mcp_system_tools():
    print("\n--- 2. Testing MCP System Tools & Telemetry ---")
    from app.mcp.system_tools import SystemTools
    info = SystemTools.get_system_info()
    print(f"System CPU: {info.get('cpu', {}).get('percent')}% | RAM: {info.get('memory', {}).get('used_percent')}%")
    assert info["status"] == "success", "Failed to get telemetry"
    
    # Test safe shell command
    shell_res = SystemTools.run_shell_command("hostname")
    print(f"Shell command (hostname): {shell_res.get('stdout', '').strip()}")
    assert shell_res["status"] == "success", "Shell command failed"
    print("[OK] SystemTools test PASSED.")

async def test_mcp_cyber_tools():
    print("\n--- 3. Testing Cyber Tools (Port Scanner & Threat Check) ---")
    from app.mcp.cyber_tools import CyberTools
    scan = await CyberTools.run_scanner("127.0.0.1", "80,443,8000")
    print(f"Port scan result on 127.0.0.1: {scan}")
    assert scan["status"] == "success", "Scanner failed"
    
    threat = await CyberTools.threat_check(ip="127.0.0.1")
    print(f"Threat check result: {threat.get('verdict')}")
    assert threat["status"] == "success", "Threat check failed"
    print("[OK] CyberTools test PASSED.")

async def test_mcp_web_search():
    print("\n--- 4. Testing Web Search Tool ---")
    from app.mcp.web_search import WebSearchTool
    search_res = await WebSearchTool.search_and_scrape("Python FastAPI low latency", max_results=2)
    print(f"Search results count: {search_res.get('count', 0)}")
    assert search_res["status"] == "success", "Web search failed"
    print("[OK] WebSearchTool test PASSED.")

async def test_rag_pipeline():
    print("\n--- 5. Testing RAG Ingestion Pipeline ---")
    from app.pipeline.rag_ingestion import rag_pipeline
    import tempfile
    
    # Create temp doc
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write("Chloe is an advanced AI system for Abhishek. It uses Groq for sub-second inference.")
        tmp_name = f.name
        
    try:
        res = await rag_pipeline.ingest_file(tmp_name, "test_chloe_doc.txt")
        print(f"Ingestion result: {res}")
        assert res["status"] == "success", "RAG ingestion failed"
        
        query_res = await rag_pipeline.query_documents("Who is Chloe built for?")
        print(f"RAG query returned {len(query_res)} results: {query_res}")
        assert len(query_res) > 0, "RAG query returned no results"
    finally:
        import os
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
    print("[OK] RAG Pipeline test PASSED.")

async def test_database_storage():
    print("\n--- 6. Testing SQLite Database & Audit Storage ---")
    from app.db.storage import db_storage
    db_storage.save_message("test_sess_1", "user", "System diagnostics", "PARTIALLY_ISOLATED")
    db_storage.save_message("test_sess_1", "assistant", "Diagnostics nominal.", "PARTIALLY_ISOLATED")
    
    messages = db_storage.get_recent_messages("test_sess_1", limit=5)
    print(f"Retrieved {len(messages)} history messages.")
    assert len(messages) >= 2, "Database message history retrieval failed"
    
    db_storage.log_tool_execution("test_sess_1", "get_system_info", {}, "success", {"cpu": 10}, "PARTIALLY_ISOLATED")
    print("[OK] Database & Audit Storage test PASSED.")

async def main():
    print("=" * 60)
    print("RUNNING PROJECT CHLOE COMPONENT TEST SUITE")
    print("=" * 60)
    
    await test_stream_buffer()
    await test_mcp_system_tools()
    await test_mcp_cyber_tools()
    await test_mcp_web_search()
    await test_rag_pipeline()
    await test_database_storage()
    
    print("\n" + "=" * 60)
    print("ALL PROJECT CHLOE 2.0 SUBSYSTEM TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
