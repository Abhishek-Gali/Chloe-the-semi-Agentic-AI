"""
Project Chloe - LangGraph Unified Persona & Tri-Mode Router
Implements the LangGraph StateGraph persona router and state management matrix
as specified in the Chloe 2.0 system architecture.
"""

import logging
from typing import Dict, Any, List, Optional, TypedDict
from langgraph.graph import StateGraph, START, END
from app.core.modes import OperatingMode
from app.core.persona import get_system_prompt
from app.config import settings

logger = logging.getLogger(__name__)

class ChloeGraphState(TypedDict):
    session_id: str
    user_text: str
    mode: str
    speak: bool
    rag_context: str
    learned_memory_context: str
    experience_context: str
    selected_model: str
    target_engine: str
    messages: List[Dict[str, str]]
    full_completion: str
    tool_calls: List[Dict[str, Any]]

class LangGraphPersonaRouter:
    """
    Unified LangGraph State Graph persona router managing tri-mode execution,
    conversation state compression, and model auto-routing.
    """
    def __init__(self):
        self.graph = self._build_graph()

    def _input_processor_node(self, state: ChloeGraphState) -> ChloeGraphState:
        """Processes input text, builds system prompt & compresses context."""
        user_text = state.get("user_text", "")
        mode_str = state.get("mode", OperatingMode.PARTIALLY_ISOLATED.value)
        rag_context = state.get("rag_context", "")
        learned_memory_context = state.get("learned_memory_context", "")
        experience_context = state.get("experience_context", "")

        try:
            mode_enum = OperatingMode(mode_str)
        except Exception:
            mode_enum = OperatingMode.PARTIALLY_ISOLATED

        system_prompt = get_system_prompt(
            mode=mode_enum,
            rag_context=rag_context,
            learned_memory_context=learned_memory_context,
            experience_context=experience_context
        )
        messages = [{"role": "system", "content": system_prompt}]
        
        # Historical messages if provided
        for msg in state.get("messages", []):
            if msg.get("role") != "system":
                messages.append(msg)
                
        messages.append({"role": "user", "content": user_text})
        state["messages"] = messages
        return state

    def _tri_mode_router_node(self, state: ChloeGraphState) -> ChloeGraphState:
        """Evaluates tri-mode execution matrix and selects specialized engine."""
        mode_str = state.get("mode", OperatingMode.PARTIALLY_ISOLATED.value)
        user_text_lower = state.get("user_text", "").lower()

        # --- Shared keyword banks ---
        CODE_KEYWORDS = [
            "code", "python", "script", "exploit", "cve", "audit", "security",
            "poc", "refactor", "bug", "function", "class", "vulnerability",
            "payload", "reverse shell", "injection", "privilege", "enumerate",
            "compile", "debug", "syntax", "algorithm", "bash", "powershell cmd"
        ]
        VISION_KEYWORDS = [
            "ocr", "image", "screenshot", "diagram", "pdf scan", "scanned",
            "architectural", "photo", "picture", "read this image", "what's in this"
        ]
        QUICK_KEYWORDS = [
            "hello", "hi", "hey", "what time", "how are you", "thanks",
            "thank you", "yes", "no", "ok", "okay", "sure", "bye", "quit"
        ]

        if mode_str == OperatingMode.FULLY_ISOLATED.value:
            # Air-Gapped: 100% local, route to right specialist
            if any(k in user_text_lower for k in VISION_KEYWORDS):
                # Vision / OCR -> qwen2.5vl:3b
                state["target_engine"] = "ollama_vision"
                state["selected_model"] = settings.OLLAMA_MODEL_VISION
            elif any(k in user_text_lower for k in CODE_KEYWORDS) and len(user_text_lower.split()) > 4:
                # Heavy Code / Security / Exploit Audit -> qwen2.5-coder:7b
                state["target_engine"] = "ollama_coder"
                state["selected_model"] = settings.OLLAMA_MODEL_CODER
            else:
                # Primary Resident Persona & Voice Brain -> chloe:latest (stays hot in RAM for <200ms TTFA)
                state["target_engine"] = "ollama_primary"
                state["selected_model"] = settings.OLLAMA_MODEL

        elif mode_str == OperatingMode.COMPLETELY_OPEN.value:
            # Frontier Cloud: Gemini for all (best reasoning + 1M context)
            state["target_engine"] = "gemini"
            state["selected_model"] = settings.GEMINI_MODEL

        else:
            # PARTIALLY_ISOLATED (Hybrid Local): Groq cloud for speed
            # Vision still uses local (Groq can't see images)
            if any(k in user_text_lower for k in VISION_KEYWORDS):
                state["target_engine"] = "ollama_vision"
                state["selected_model"] = settings.OLLAMA_MODEL_VISION
            else:
                state["target_engine"] = "groq"
                state["selected_model"] = settings.GROQ_LLM_MODEL

        logger.info(f"LangGraphRouter: [{state.get('session_id')}] Mode={mode_str} -> Engine={state['target_engine']} ({state['selected_model']})")
        return state

    def _build_graph(self):
        builder = StateGraph(ChloeGraphState)
        builder.add_node("input_processor", self._input_processor_node)
        builder.add_node("tri_mode_router", self._tri_mode_router_node)

        builder.add_edge(START, "input_processor")
        builder.add_edge("input_processor", "tri_mode_router")
        builder.add_edge("tri_mode_router", END)

        return builder.compile()

    def process_route(
        self,
        session_id: str,
        user_text: str,
        mode: str,
        rag_context: str = "",
        learned_memory_context: str = "",
        experience_context: str = "",
        speak: bool = True,
        history_messages: Optional[List[Dict[str, str]]] = None
    ) -> ChloeGraphState:
        initial_state: ChloeGraphState = {
            "session_id": session_id,
            "user_text": user_text,
            "mode": mode,
            "speak": speak,
            "rag_context": rag_context,
            "learned_memory_context": learned_memory_context,
            "experience_context": experience_context,
            "selected_model": settings.OLLAMA_MODEL,
            "target_engine": "ollama_primary",
            "messages": history_messages or [],
            "full_completion": "",
            "tool_calls": []
        }
        return self.graph.invoke(initial_state)

chloe_langgraph_router = LangGraphPersonaRouter()
