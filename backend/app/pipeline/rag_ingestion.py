"""
Project Chloe - Split-Path Fast RAG Ingestion & Vector Retrieval
Extracts text from documents, chunks text, and stores embeddings in persistent ChromaDB.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class RAGPipeline:
    def __init__(self):
        self.persist_dir = settings.CHROMA_PERSIST_DIR
        self.client = None
        self.collection = None
        self.fallback_docs: List[Dict[str, Any]] = []
        self._init_chroma()

    def _init_chroma(self):
        """Initializes ChromaDB persistent client and collection."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings
            
            self.client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = self.client.get_or_create_collection(
                name="chloe_vault",
                metadata={"description": "Project Chloe Document Knowledge Vault"}
            )
            logger.info("RAGPipeline: ChromaDB persistent vector collection initialized.")
        except Exception as e:
            logger.warning(f"RAGPipeline: ChromaDB init error ({e}), using in-memory semantic fallback.")
            self.client = None
            self.collection = None

    def extract_ocr_with_qwen_vl(self, image_path: str) -> str:
        """Uses local Qwen2.5-VL model (qwen2.5vl:3b) to perform high-precision OCR on image files and scanned documents."""
        try:
            import base64
            import requests
            
            with open(image_path, "rb") as f:
                b64_data = base64.b64encode(f.read()).decode("utf-8")
                
            payload = {
                "model": getattr(settings, "OLLAMA_MODEL_VISION", "qwen2.5vl:3b"),
                "messages": [
                    {
                        "role": "user",
                        "content": "Perform high-precision OCR on this document image. Transcribe all text, tables, headers, and architectural diagrams into clean Markdown format.",
                        "images": [b64_data]
                    }
                ],
                "stream": False
            }
            res = requests.post(f"{settings.OLLAMA_HOST}/api/chat", json=payload, timeout=45)
            if res.status_code == 200:
                data = res.json()
                ocr_text = data.get("message", {}).get("content", "")
                if ocr_text:
                    logger.info(f"RAGPipeline: Successfully performed Qwen-VL OCR on {Path(image_path).name}.")
                    return ocr_text
        except Exception as e:
            logger.warning(f"RAGPipeline: Qwen-VL OCR extraction skipped ({e}).")
        return ""

    def extract_text_from_file(self, file_path: str) -> str:
        """Extracts plain text from various file formats (.pdf, .txt, .md, .py, .png, .jpg, etc.)."""
        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp"]:
                return self.extract_ocr_with_qwen_vl(file_path)

            elif ext == ".pdf":
                extracted_text = ""
                try:
                    import pypdf
                    reader = pypdf.PdfReader(str(path))
                    text_parts = [page.extract_text() for page in reader.pages if page.extract_text()]
                    extracted_text = "\n\n".join(text_parts).strip()
                except Exception:
                    try:
                        import PyPDF2
                        reader = PyPDF2.PdfReader(str(path))
                        text_parts = [page.extract_text() for page in reader.pages if page.extract_text()]
                        extracted_text = "\n\n".join(text_parts).strip()
                    except Exception as e:
                        logger.error(f"Failed to extract PDF text: {e}")

                if not extracted_text:
                    logger.info(f"RAGPipeline: PDF {path.name} appears to be a scanned image. Routing to Qwen2.5-VL OCR...")
                    extracted_text = self.extract_ocr_with_qwen_vl(file_path)

                return extracted_text
            else:
                # Text-based file formats (.txt, .md, .py, .json, .csv, etc.)
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return ""

    def chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 100) -> List[str]:
        """Splits long text into semantic chunks using LlamaIndex SentenceSplitter with fallback."""
        if not text:
            return []
        
        try:
            from llama_index.core.node_parser import SentenceSplitter
            splitter = SentenceSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
            nodes = splitter.split_text(text)
            if nodes:
                return [n.strip() for n in nodes if n.strip()]
        except Exception as e:
            logger.debug(f"RAGPipeline: LlamaIndex SentenceSplitter fallback to character window: {e}")

        chunks = []
        start = 0
        text_len = len(text)
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += (chunk_size - overlap)
            
        return chunks

    async def ingest_file(self, file_path: str, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        Fast-Path: Ingests a file, extracts text, chunks it, and indexes into ChromaDB.
        """
        name = filename or Path(file_path).name
        raw_text = self.extract_text_from_file(file_path)
        if not raw_text:
            return {"status": "error", "message": f"No text could be extracted from {name}."}

        chunks = self.chunk_text(raw_text)
        if not chunks:
            return {"status": "error", "message": "File produced 0 chunks."}

        file_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:12]
        char_count = len(raw_text)
        approx_tokens = len(raw_text.split())

        if self.collection:
            ids = [f"{file_hash}_chunk_{i}" for i in range(len(chunks))]
            metadatas = [{"source": name, "chunk_index": i, "file_hash": file_hash, "char_count": char_count} for i in range(len(chunks))]
            
            self.collection.upsert(
                documents=chunks,
                metadatas=metadatas,
                ids=ids
            )
        else:
            # Fallback memory store
            for i, chunk in enumerate(chunks):
                self.fallback_docs.append({
                    "id": f"{file_hash}_chunk_{i}",
                    "source": name,
                    "text": chunk,
                    "char_count": char_count
                })

        logger.info(f"RAGPipeline: Ingested {len(chunks)} chunks for {name}.")
        return {
            "status": "success",
            "filename": name,
            "chunks_indexed": len(chunks),
            "characters": char_count,
            "approx_tokens": approx_tokens,
            "file_hash": file_hash,
            "preview": raw_text[:200]
        }

    def get_vault_stats(self) -> Dict[str, Any]:
        """
        Retrieves real-time ChromaDB vector collection metrics and document inventory.
        """
        doc_stats = {}
        total_chunks = 0
        
        if self.collection:
            try:
                total_chunks = self.collection.count()
                # Get all metadata
                data = self.collection.get(include=["metadatas"])
                metadatas = data.get("metadatas", [])
                
                for meta in metadatas:
                    source = meta.get("source", "Unknown Document")
                    if source not in doc_stats:
                        doc_stats[source] = {
                            "source": source,
                            "chunks": 0,
                            "file_hash": meta.get("file_hash", ""),
                            "char_count": meta.get("char_count", 0)
                        }
                    doc_stats[source]["chunks"] += 1
            except Exception as e:
                logger.error(f"Error fetching ChromaDB stats: {e}")
        else:
            total_chunks = len(self.fallback_docs)
            for doc in self.fallback_docs:
                src = doc.get("source", "Unknown")
                if src not in doc_stats:
                    doc_stats[src] = {"source": src, "chunks": 0, "file_hash": "", "char_count": 0}
                doc_stats[src]["chunks"] += 1

        docs_list = list(doc_stats.values())
        return {
            "status": "success",
            "total_chunks": total_chunks,
            "total_documents": len(docs_list),
            "documents": docs_list,
            "engine": "ChromaDB Persistent Vector Vault" if self.collection else "In-Memory Semantic Fallback"
        }

    def delete_document(self, filename: str) -> Dict[str, Any]:
        """
        Deletes all chunks belonging to a specific document from ChromaDB.
        """
        deleted_count = 0
        if self.collection:
            try:
                # Delete by where filter on metadata source
                self.collection.delete(where={"source": filename})
                logger.info(f"RAGPipeline: Deleted all chunks for '{filename}' from ChromaDB.")
                return {"status": "success", "message": f"Document '{filename}' removed from ChromaDB vector vault."}
            except Exception as e:
                logger.error(f"Error deleting document from ChromaDB: {e}")
                return {"status": "error", "message": str(e)}
        else:
            initial = len(self.fallback_docs)
            self.fallback_docs = [d for d in self.fallback_docs if d.get("source") != filename]
            deleted_count = initial - len(self.fallback_docs)
            return {"status": "success", "message": f"Removed {deleted_count} chunks for '{filename}'."}

    def flush_vault(self) -> Dict[str, Any]:
        """
        Completely drops and recreates the ChromaDB vector vault and clears in-memory documents.
        """
        try:
            if self.client:
                try:
                    self.client.delete_collection("chloe_vault")
                except Exception:
                    pass
                self._init_chroma()
            self.fallback_docs.clear()
            logger.info("RAGPipeline: ChromaDB vector vault flushed and reset to 0.")
            return {"status": "success", "message": "All document embeddings flushed from ChromaDB."}
        except Exception as e:
            logger.error(f"Error flushing ChromaDB vault: {e}")
            return {"status": "error", "message": str(e)}

    async def query_documents(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Queries ChromaDB for semantically relevant chunks matching query.
        """
        if not query:
            return []

        if self.collection:
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k
                )
                
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                
                formatted = []
                for doc, meta in zip(docs, metas):
                    formatted.append({
                        "content": doc,
                        "source": meta.get("source", "Unknown"),
                        "chunk_index": meta.get("chunk_index", 0)
                    })
                return formatted
            except Exception as e:
                logger.error(f"ChromaDB query error: {e}")

        # Fallback keyword match
        query_words = set(query.lower().split())
        scored = []
        for item in self.fallback_docs:
            text_lower = item["text"].lower()
            overlap = sum(1 for w in query_words if w in text_lower)
            if overlap > 0:
                scored.append((overlap, item))
                
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{"content": item["text"], "source": item["source"]} for _, item in scored[:top_k]]

rag_pipeline = RAGPipeline()
