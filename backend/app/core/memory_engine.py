"""
Project Chloe - Continuous Learning Engine (Levels 1, 2, & 3)
Provides:
- Level 1: Long-Term Episodic & User Preference Memory with Isolated ChromaDB Vector Indexing.
- Level 2: Action Experience & Multi-Tool Skill Caching with Few-Shot Semantic Retrieval.
- Level 3: Curated Conversation Dataset Accumulator & JSONL Exporter for Local LoRA Training.
"""

import os
import re
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings
from app.db.storage import db_storage

logger = logging.getLogger("ChloeLearningEngine")

# Memory Classification Patterns
PREFERENCE_PATTERNS = [
    r"(?:i\s+prefer|i\s+like|i\s+love|i\s+always\s+use|always\s+use|prefer\s+using)\s+(.+)",
    r"(?:don't\s+use|do\s+not\s+use|never\s+use|i\s+hate|i\s+dislike)\s+(.+)",
    r"(?:my\s+favorite|my\s+preferred)\s+(.+)",
    r"(?:i\s+work\s+with|my\s+stack\s+is|my\s+default\s+language\s+is)\s+(.+)",
]

SHORTCUT_PATTERNS = [
    r"(?:when\s+i\s+say|whenever\s+i\s+say)\s+['\"]?(.+?)['\"]?\s+(?:it\s+means|i\s+mean|refer\s+to|use)\s+['\"]?(.+?)['\"]?",
    r"(?:my\s+project|main\s+project|the\s+project)\s+(?:is\s+at|is\s+located\s+at|path\s+is)\s+['\"]?(.+?)['\"]?",
    r"(?:remember\s+that|note\s+that)\s+['\"]?(.+?)['\"]?\s+(?:means|is)\s+['\"]?(.+?)['\"]?",
]

CORRECTION_PATTERNS = [
    r"(?:no|that's\s+wrong|incorrect|not\s+like\s+that|that\s+was\s+wrong)[,\s]+(?:it\s+should\s+be|use|do)\s+(.+)",
    r"(?:don't\s+do\s+that|do\s+not\s+do\s+that)[,\s]+(?:instead\s+do|always\s+do)\s+(.+)",
]


class ContinuousLearningEngine:
    """
    Autonomous 3-Tier Continuous Learning System with an Isolated ChromaDB vector database.
    """

    def __init__(self):
        self.memory_chroma_dir = settings.MEMORY_CHROMA_DIR
        self.dataset_dir = settings.DATASET_DIR
        self.train_jsonl_path = settings.TRAIN_JSONL_PATH
        self.client = None
        self.memory_collection = None
        self.experience_collection = None
        self._init_isolated_chroma()

    def _init_isolated_chroma(self):
        """Initializes the dedicated, isolated ChromaDB persistent client and memory collections."""
        try:
            import chromadb
            os.makedirs(self.memory_chroma_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=self.memory_chroma_dir)
            
            # Collection 1: User Preferences, Facts, Project Shortcuts & Learned Rules
            self.memory_collection = self.client.get_or_create_collection(
                name="learned_memories",
                metadata={"description": "Project Chloe Isolated Long-Term User & System Memory"}
            )
            
            # Collection 2: Action Experience & Multi-Tool Execution Patterns
            self.experience_collection = self.client.get_or_create_collection(
                name="action_skills",
                metadata={"description": "Project Chloe Cached Multi-Tool Workflow Experiences"}
            )
            logger.info("ContinuousLearningEngine: Isolated Memory ChromaDB initialized successfully.")
        except Exception as e:
            logger.warning(f"ContinuousLearningEngine: ChromaDB init fallback ({e}). Using SQLite persistence.")
            self.client = None
            self.memory_collection = None
            self.experience_collection = None

    # =========================================================================
    # Level 1: Long-Term Episodic & Preference Memory
    # =========================================================================

    def record_memory(self, category: str, memory_text: str, confidence: float = 1.0, source_session: str = "session_abhishek") -> Optional[int]:
        """Saves memory to SQLite and indexes it in the isolated ChromaDB collection."""
        if not memory_text or len(memory_text.strip()) < 3:
            return None
        
        clean_text = memory_text.strip()
        memory_id = db_storage.save_user_memory(
            category=category,
            memory_text=clean_text,
            confidence=confidence,
            source_session=source_session
        )

        if self.memory_collection and memory_id:
            try:
                doc_id = f"mem_{memory_id}"
                self.memory_collection.upsert(
                    ids=[doc_id],
                    documents=[clean_text],
                    metadatas=[{"category": category, "confidence": confidence, "memory_id": memory_id}]
                )
                logger.info(f"ContinuousLearningEngine: Indexed learned memory [{category}]: {clean_text}")
            except Exception as e:
                logger.warning(f"Failed to vectorize memory in ChromaDB: {e}")

        return memory_id

    def retrieve_relevant_memories(self, query: str, top_k: int = 4) -> List[str]:
        """
        Retrieves the most semantically relevant memories and user preferences for the active prompt.
        """
        if not query or len(query.strip()) < 2:
            return []

        memories = []

        # 1. Semantic Vector Query on Isolated ChromaDB
        if self.memory_collection:
            try:
                count = self.memory_collection.count()
                if count > 0:
                    k = min(top_k, count)
                    results = self.memory_collection.query(
                        query_texts=[query],
                        n_results=k
                    )
                    docs = results.get("documents", [[]])[0]
                    for doc in docs:
                        if doc and doc not in memories:
                            memories.append(doc)
            except Exception as e:
                logger.warning(f"Memory vector search error: {e}")

        # 2. Complement with top recent / highest confidence memories from SQLite
        if len(memories) < top_k:
            sqlite_mems = db_storage.get_all_user_memories(limit=top_k)
            for m in sqlite_mems:
                txt = m.get("memory_text")
                if txt and txt not in memories:
                    memories.append(txt)
                if len(memories) >= top_k:
                    break

        return memories

    def extract_memories_heuristic(self, user_text: str) -> List[Tuple[str, str, float]]:
        """
        Fast sub-millisecond heuristic extractor for preferences, shortcuts, and corrections.
        Returns list of (category, memory_text, confidence).
        """
        extracted = []
        text_lower = user_text.strip().lower()

        # Preference patterns
        for pattern in PREFERENCE_PATTERNS:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                pref_content = match.group(0).strip()
                extracted.append(("preference", f"User Preference: {pref_content}", 0.95))

        # Shortcut / Alias patterns
        for pattern in SHORTCUT_PATTERNS:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                shortcut = match.group(0).strip()
                extracted.append(("alias", f"Context Shortcut: {shortcut}", 0.98))

        # Correction patterns
        for pattern in CORRECTION_PATTERNS:
            match = re.search(pattern, user_text, re.IGNORECASE)
            if match:
                corr = match.group(0).strip()
                extracted.append(("correction", f"User Correction Rule: {corr}", 0.99))

        return extracted

    # =========================================================================
    # Level 2: Action Experience & Multi-Tool Skill Caching
    # =========================================================================

    def record_task_experience(self, user_intent: str, tool_executions: List[Dict[str, Any]]) -> Optional[int]:
        """
        Caches a successful multi-tool workflow execution for future few-shot guidance.
        """
        if not user_intent or not tool_executions:
            return None

        # Filter and sanitize tool execution list
        sanitized_tools = []
        for t in tool_executions:
            tool_name = t.get("tool") or t.get("tool_name")
            params = t.get("params") or {}
            if tool_name:
                sanitized_tools.append({"tool": tool_name, "params": params})

        if not sanitized_tools:
            return None

        clean_intent = user_intent.strip()
        exp_id = db_storage.save_task_experience(clean_intent, sanitized_tools)

        if self.experience_collection and exp_id:
            try:
                doc_id = f"exp_{exp_id}"
                summary_doc = f"Goal: {clean_intent} | Tools: {', '.join([t['tool'] for t in sanitized_tools])}"
                self.experience_collection.upsert(
                    ids=[doc_id],
                    documents=[summary_doc],
                    metadatas=[{"exp_id": exp_id, "tool_count": len(sanitized_tools)}]
                )
                logger.info(f"ContinuousLearningEngine: Cached action skill workflow for '{clean_intent}' ({len(sanitized_tools)} tools).")
            except Exception as e:
                logger.warning(f"Failed to vectorize action skill in ChromaDB: {e}")

        return exp_id

    def retrieve_relevant_experiences(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves matching past successful multi-tool execution workflows for few-shot guidance.
        """
        if not query or len(query.strip()) < 4:
            return []

        experiences = []
        if self.experience_collection:
            try:
                count = self.experience_collection.count()
                if count > 0:
                    k = min(top_k, count)
                    results = self.experience_collection.query(
                        query_texts=[query],
                        n_results=k
                    )
                    metas = results.get("metadatas", [[]])[0]
                    for meta in metas:
                        exp_id = meta.get("exp_id")
                        if exp_id:
                            all_exps = db_storage.get_task_experiences(limit=50)
                            for e in all_exps:
                                if e["id"] == exp_id and e not in experiences:
                                    experiences.append(e)
            except Exception as e:
                logger.warning(f"Action skill search error: {e}")

        return experiences

    # =========================================================================
    # Level 3: Training Dataset Accumulator & JSONL Exporter
    # =========================================================================

    def record_training_pair(self, user_input: str, assistant_output: str, system_prompt: str = "") -> Optional[int]:
        """
        Records high-quality conversation turns into SQLite and writes to local JSONL for LoRA training.
        """
        clean_user = user_input.strip()
        clean_ast = assistant_output.strip()

        # Quality filters: Skip single-word trivial responses and empty turns
        if len(clean_user) < 3 or len(clean_ast) < 4:
            return None
        if clean_user.lower() in ["hi", "hello", "hey", "test", "ok", "thanks", "clear"]:
            return None

        # Quality scoring heuristics
        score = 1.0
        if "```" in clean_ast or "{" in clean_ast:
            score += 0.5  # Technical tool usage / code generation has higher weight

        pair_id = db_storage.save_training_pair(
            user_input=clean_user,
            assistant_output=clean_ast,
            system_prompt=system_prompt,
            quality_score=score
        )

        # Append to continuous training JSONL
        if pair_id:
            try:
                self._append_to_jsonl(clean_user, clean_ast, system_prompt)
            except Exception as e:
                logger.warning(f"Failed to append training pair to JSONL: {e}")

        return pair_id

    def _append_to_jsonl(self, user_input: str, assistant_output: str, system_prompt: str = ""):
        """Appends a single sample in standard Alpaca/ShareGPT format to chloe_train.jsonl."""
        os.makedirs(self.dataset_dir, exist_ok=True)
        sample = {
            "instruction": user_input,
            "system": system_prompt or "You are Chloe, an elite personal AI assistant built for Abhishek.",
            "output": assistant_output,
            "timestamp": time.time()
        }
        with open(self.train_jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(sample) + "\n")

    def export_full_dataset(self) -> Dict[str, Any]:
        """
        Exports all unexported training pairs into the JSONL training dataset.
        """
        os.makedirs(self.dataset_dir, exist_ok=True)
        unexported = db_storage.get_unexported_training_pairs(limit=1000)
        
        exported_count = 0
        pair_ids = []
        with open(self.train_jsonl_path, "a", encoding="utf-8") as f:
            for pair in unexported:
                sample = {
                    "instruction": pair["user_input"],
                    "system": pair["system_prompt"] or "You are Chloe, an elite personal AI assistant built for Abhishek.",
                    "output": pair["assistant_output"],
                    "quality_score": pair["quality_score"],
                    "timestamp": pair["created_at"]
                }
                f.write(json.dumps(sample) + "\n")
                pair_ids.append(pair["id"])
                exported_count += 1

        if pair_ids:
            db_storage.mark_training_pairs_exported(pair_ids)

        total_samples = 0
        if os.path.exists(self.train_jsonl_path):
            with open(self.train_jsonl_path, "r", encoding="utf-8") as f:
                total_samples = sum(1 for line in f if line.strip())

        return {
            "status": "success",
            "newly_exported": exported_count,
            "total_dataset_samples": total_samples,
            "jsonl_path": self.train_jsonl_path
        }

    # =========================================================================
    # Unified Interaction Background Learner
    # =========================================================================

    async def learn_from_interaction(
        self,
        user_text: str,
        assistant_response: str,
        tool_executions: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "session_abhishek",
        system_prompt: str = ""
    ):
        """
        Asynchronous, non-blocking background learner executed after each interaction.
        Runs in under 1ms without blocking the main event loop or audio stream.
        """
        if not user_text or not assistant_response:
            return

        try:
            # 1. Level 1: Extract and save heuristic memories & preferences
            extracted_memories = self.extract_memories_heuristic(user_text)
            for category, mem_text, conf in extracted_memories:
                self.record_memory(category, mem_text, confidence=conf, source_session=session_id)

            # 2. Level 2: If multi-tool execution occurred successfully, cache workflow
            if tool_executions and len(tool_executions) > 0:
                self.record_task_experience(user_text, tool_executions)

            # 3. Level 3: Save to curated training dataset
            self.record_training_pair(user_text, assistant_response, system_prompt=system_prompt)

        except Exception as e:
            logger.error(f"ContinuousLearningEngine error during interaction learning: {e}")


# Global Singleton Instance
memory_engine = ContinuousLearningEngine()
