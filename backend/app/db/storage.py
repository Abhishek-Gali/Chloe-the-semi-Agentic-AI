"""
Project Chloe - Database & Session Persistence
Provides SQLite storage for audit trails, messages, and document registry,
along with an in-memory / Redis cache for real-time session state.
"""

import sqlite3
import json
import time
import logging
from typing import Dict, Any, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class DatabaseStorage:
    def __init__(self):
        self.db_path = settings.DB_PATH
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initializes tables for conversation history, audit logs, and file vault."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Conversation logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # Tool audit logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tool_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    params TEXT,
                    status TEXT,
                    result TEXT,
                    mode TEXT NOT NULL,
                    timestamp REAL NOT NULL
                )
            """)

            # Document index
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault_registry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    file_hash TEXT UNIQUE NOT NULL,
                    size_bytes INTEGER,
                    vault_path TEXT,
                    timestamp REAL NOT NULL
                )
            """)

            # Continuous Learning - Level 1: Long-Term Episodic & User Preference Memory
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    memory_text TEXT NOT NULL,
                    confidence REAL DEFAULT 1.0,
                    source_session TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)

            # Continuous Learning - Level 2: Action Skill & Experience Cache
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_experiences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_intent TEXT NOT NULL,
                    tool_sequence_json TEXT NOT NULL,
                    success_count INTEGER DEFAULT 1,
                    created_at REAL NOT NULL,
                    last_executed_at REAL NOT NULL
                )
            """)

            # Continuous Learning - Level 3: Curated Training Pairs for LoRA Fine-Tuning
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS curated_training_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    system_prompt TEXT,
                    user_input TEXT NOT NULL,
                    assistant_output TEXT NOT NULL,
                    quality_score REAL DEFAULT 1.0,
                    exported_to_jsonl INTEGER DEFAULT 0,
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def get_last_created_file(self) -> Optional[str]:
        """Returns the most recent valid file or directory path written/created by Chloe."""
        import os
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT params, tool_name FROM tool_audit_logs WHERE tool_name IN ('write_file', 'create_folder') AND status = 'success' ORDER BY id DESC LIMIT 10"
                )
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        p = json.loads(row[0]) if row[0] else {}
                        path_val = p.get("path")
                        if path_val and os.path.exists(path_val):
                            return path_val
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def save_message(self, session_id: str, role: str, content: str, mode: str):
        if not content or not content.strip():
            return
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO conversation_history (session_id, role, content, mode, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (session_id, role, content, mode, time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving message: {e}")

    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT role, content, mode, timestamp FROM conversation_history WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit)
                )
                rows = cursor.fetchall()
                messages = []
                last_msg = None
                for row in reversed(rows):
                    role = row[0]
                    content = row[1]
                    
                    # 1. Skip empty content messages
                    if not content or not content.strip():
                        continue
                        
                    # 2. Skip consecutive duplicates of the same role
                    if last_msg and last_msg["role"] == role and last_msg["content"].strip().lower() == content.strip().lower():
                        continue
                        
                    msg = {
                        "role": role,
                        "content": content,
                        "mode": row[2],
                        "timestamp": row[3]
                    }
                    messages.append(msg)
                    last_msg = msg
                return messages
        except Exception as e:
            logger.error(f"Error reading messages: {e}")
            return []

    def log_tool_execution(self, session_id: str, tool_name: str, params: Dict[str, Any], status: str, result: Any, mode: str):
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT INTO tool_audit_logs (session_id, tool_name, params, status, result, mode, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (session_id, tool_name, json.dumps(params), status, json.dumps(result) if isinstance(result, (dict, list)) else str(result), mode, time.time())
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error logging tool execution: {e}")

    def clear_all_history(self):
        """Clears all conversation messages and tool logs for a complete flush."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM conversation_history")
                conn.commit()
            logger.info("DatabaseStorage: Cleared all conversation history.")
        except Exception as e:
            logger.error(f"Error clearing conversation history: {e}")

    def clear_session_history(self, session_id: str):
        """Clears conversation history for a specific session."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM conversation_history WHERE session_id = ?", (session_id,))
                conn.commit()
            logger.info(f"DatabaseStorage: Cleared history for session {session_id}.")
        except Exception as e:
            logger.error(f"Error clearing session history: {e}")

    # ==========================================
    # Continuous Learning CRUD & Persistence API
    # ==========================================

    def save_user_memory(self, category: str, memory_text: str, confidence: float = 1.0, source_session: str = "session_abhishek") -> Optional[int]:
        """Saves or updates a permanent learned fact, preference, shortcut or instruction."""
        if not memory_text or not memory_text.strip():
            return None
        text_clean = memory_text.strip()
        now = time.time()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # Check for existing duplicate memory to update timestamp and confidence
                cursor.execute(
                    "SELECT id FROM user_memories WHERE category = ? AND LOWER(memory_text) = LOWER(?)",
                    (category, text_clean)
                )
                row = cursor.fetchone()
                if row:
                    memory_id = row[0]
                    cursor.execute(
                        "UPDATE user_memories SET confidence = MAX(confidence, ?), updated_at = ? WHERE id = ?",
                        (confidence, now, memory_id)
                    )
                    conn.commit()
                    return memory_id
                else:
                    cursor.execute(
                        "INSERT INTO user_memories (category, memory_text, confidence, source_session, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                        (category, text_clean, confidence, source_session, now, now)
                    )
                    conn.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving user memory: {e}")
            return None

    def get_all_user_memories(self, category: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Retrieves learned user memories, sorted by recency and confidence."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if category:
                    cursor.execute(
                        "SELECT id, category, memory_text, confidence, source_session, created_at, updated_at FROM user_memories WHERE category = ? ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                        (category, limit)
                    )
                else:
                    cursor.execute(
                        "SELECT id, category, memory_text, confidence, source_session, created_at, updated_at FROM user_memories ORDER BY confidence DESC, updated_at DESC LIMIT ?",
                        (limit,)
                    )
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "category": r[1],
                        "memory_text": r[2],
                        "confidence": r[3],
                        "source_session": r[4],
                        "created_at": r[5],
                        "updated_at": r[6]
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Error retrieving user memories: {e}")
            return []

    def delete_user_memory(self, memory_id: int) -> bool:
        """Deletes a specific learned memory by ID."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM user_memories WHERE id = ?", (memory_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting user memory {memory_id}: {e}")
            return False

    def save_task_experience(self, user_intent: str, tool_sequence: List[Dict[str, Any]]) -> Optional[int]:
        """Caches a successful multi-tool workflow execution for future few-shot repetition."""
        if not user_intent or not tool_sequence:
            return None
        now = time.time()
        intent_clean = user_intent.strip()
        seq_json = json.dumps(tool_sequence)
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, success_count FROM task_experiences WHERE LOWER(user_intent) = LOWER(?)",
                    (intent_clean,)
                )
                row = cursor.fetchone()
                if row:
                    exp_id, count = row[0], row[1]
                    cursor.execute(
                        "UPDATE task_experiences SET tool_sequence_json = ?, success_count = ?, last_executed_at = ? WHERE id = ?",
                        (seq_json, count + 1, now, exp_id)
                    )
                    conn.commit()
                    return exp_id
                else:
                    cursor.execute(
                        "INSERT INTO task_experiences (user_intent, tool_sequence_json, success_count, created_at, last_executed_at) VALUES (?, ?, 1, ?, ?)",
                        (intent_clean, seq_json, now, now)
                    )
                    conn.commit()
                    return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving task experience: {e}")
            return None

    def get_task_experiences(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves cached task workflows sorted by execution frequency."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, user_intent, tool_sequence_json, success_count, created_at, last_executed_at FROM task_experiences ORDER BY success_count DESC, last_executed_at DESC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    try:
                        seq = json.loads(r[2])
                    except Exception:
                        seq = []
                    results.append({
                        "id": r[0],
                        "user_intent": r[1],
                        "tool_sequence": seq,
                        "success_count": r[3],
                        "created_at": r[4],
                        "last_executed_at": r[5]
                    })
                return results
        except Exception as e:
            logger.error(f"Error retrieving task experiences: {e}")
            return []

    def save_training_pair(self, user_input: str, assistant_output: str, system_prompt: str = "", quality_score: float = 1.0) -> Optional[int]:
        """Saves a high-quality conversation turn for future LoRA fine-tuning dataset generation."""
        if not user_input or not assistant_output or len(user_input.strip()) < 3:
            return None
        now = time.time()
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO curated_training_pairs (system_prompt, user_input, assistant_output, quality_score, exported_to_jsonl, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                    (system_prompt, user_input.strip(), assistant_output.strip(), quality_score, now)
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Error saving training pair: {e}")
            return None

    def get_unexported_training_pairs(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Retrieves curated training pairs that haven't been compiled to JSONL yet."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, system_prompt, user_input, assistant_output, quality_score, created_at FROM curated_training_pairs WHERE exported_to_jsonl = 0 ORDER BY id ASC LIMIT ?",
                    (limit,)
                )
                rows = cursor.fetchall()
                return [
                    {
                        "id": r[0],
                        "system_prompt": r[1],
                        "user_input": r[2],
                        "assistant_output": r[3],
                        "quality_score": r[4],
                        "created_at": r[5]
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error(f"Error fetching unexported training pairs: {e}")
            return []

    def mark_training_pairs_exported(self, pair_ids: List[int]):
        """Marks training pairs as exported to JSONL."""
        if not pair_ids:
            return
        try:
            with self._get_connection() as conn:
                placeholders = ",".join("?" * len(pair_ids))
                conn.execute(f"UPDATE curated_training_pairs SET exported_to_jsonl = 1 WHERE id IN ({placeholders})", pair_ids)
                conn.commit()
        except Exception as e:
            logger.error(f"Error marking training pairs as exported: {e}")

    def get_learning_stats(self) -> Dict[str, Any]:
        """Returns summary statistics across all continuous learning tiers."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM user_memories")
                total_memories = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM task_experiences")
                total_experiences = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM curated_training_pairs")
                total_training_pairs = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM curated_training_pairs WHERE exported_to_jsonl = 1")
                exported_pairs = cursor.fetchone()[0]
                
                return {
                    "total_memories": total_memories,
                    "total_experiences": total_experiences,
                    "total_training_pairs": total_training_pairs,
                    "exported_training_pairs": exported_pairs
                }
        except Exception as e:
            logger.error(f"Error getting learning stats: {e}")
            return {
                "total_memories": 0,
                "total_experiences": 0,
                "total_training_pairs": 0,
                "exported_training_pairs": 0
            }

class SessionCache:
    """Fast Redis session cache with in-memory fallback for real-time session state."""
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self.redis_client = None
        try:
            import redis
            self.redis_client = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=1.0)
            self.redis_client.ping()
            logger.info("SessionCache: Connected to local Redis server.")
        except Exception:
            self.redis_client = None
            logger.info("SessionCache: Local Redis server unavailable; utilizing fast in-memory cache fallback.")

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        if self.redis_client:
            try:
                val_str = json.dumps(value) if isinstance(value, (dict, list)) else str(value)
                if ttl:
                    self.redis_client.setex(key, ttl, val_str)
                else:
                    self.redis_client.set(key, val_str)
                return
            except Exception:
                pass

        self._cache[key] = {
            "value": value,
            "expiry": time.time() + ttl if ttl else None
        }

    def get(self, key: str) -> Optional[Any]:
        if self.redis_client:
            try:
                val = self.redis_client.get(key)
                if val:
                    try:
                        return json.loads(val)
                    except Exception:
                        return val.decode("utf-8")
            except Exception:
                pass

        item = self._cache.get(key)
        if not item:
            return None
        if item["expiry"] and time.time() > item["expiry"]:
            del self._cache[key]
            return None
        return item["value"]

    def delete(self, key: str):
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception:
                pass
        if key in self._cache:
            del self._cache[key]

db_storage = DatabaseStorage()
session_cache = SessionCache()
