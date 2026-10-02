"""
Project Chloe - Agentic Orchestrator & State Machine
Coordinates LLM inference across 3 operating modes (Ollama, Groq, Gemini 2.0 via google-genai),
manages memory checkpoints, integrates RAG semantic context, and executes autonomous MCP tool loops.
"""

import json
import re
import asyncio
import logging
import aiohttp
from typing import AsyncGenerator, Dict, Any, List, Optional

from app.config import settings
from app.core.modes import OperatingMode
from app.core.persona import get_system_prompt
from app.core.langgraph_router import chloe_langgraph_router
from app.pipeline.rag_ingestion import rag_pipeline
from app.db.storage import db_storage, session_cache
from app.audio.stream_buffer import SentenceStreamBuffer
from app.audio.tts_engine import tts_engine

logger = logging.getLogger(__name__)

class ChloeOrchestrator:
    def __init__(self):
        self.groq_client = None
        self.gemini_client = None
        self.reload_clients()

    def reload_clients(self):
        """Reloads Groq and Gemini clients when settings/keys are updated."""
        if settings.GROQ_API_KEY:
            try:
                from groq import Groq
                self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("Orchestrator: Groq client initialized successfully.")
            except Exception as e:
                logger.warning(f"Orchestrator: Groq client init failed: {e}")
                self.groq_client = None
        else:
            self.groq_client = None

        if settings.GEMINI_API_KEY:
            try:
                from google import genai
                self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
                logger.info("Orchestrator: Google Gemini client initialized successfully.")
            except Exception as e:
                logger.warning(f"Orchestrator: Gemini client init failed: {e}")
                self.gemini_client = None
        else:
            self.gemini_client = None

    async def _call_ollama_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        images: Optional[List[str]] = None
    ) -> AsyncGenerator[str, None]:
        """Streams responses from local Ollama service using specialized Qwen model routing."""
        target_model = model or settings.OLLAMA_MODEL
        url = f"{settings.OLLAMA_HOST}/api/chat"
        
        # Prepare messages payload, adding image b64 if present for vision tasks
        formatted_messages = []
        for m in messages:
            msg_obj = {"role": m["role"], "content": m["content"]}
            if images and m["role"] == "user":
                msg_obj["images"] = images
            formatted_messages.append(msg_obj)

        payload = {
            "model": target_model,
            "messages": formatted_messages,
            "stream": True,
            "keep_alive": "2m",
            "options": {"temperature": 0.3, "num_ctx": 2048}
        }
        connected = False
        try:
            timeout_cfg = aiohttp.ClientTimeout(connect=3.0, total=35.0)
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=timeout_cfg) as resp:
                    if resp.status == 200:
                        connected = True
                        async for line in resp.content:
                            if line:
                                try:
                                    data = json.loads(line.decode("utf-8"))
                                    msg = data.get("message", {})
                                    content = msg.get("content", "")
                                    if content:
                                        yield content
                                except Exception:
                                    continue
                    else:
                        logger.warning(f"Ollama ({target_model}) HTTP {resp.status}")
        except Exception as e:
            logger.warning(f"Ollama connection issue for model {target_model}: {e}")

        if not connected:
            # Fallback to offline rule-based handler
            async for token in self._offline_fallback_response(messages):
                yield token

    async def _call_coder_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Streams responses specifically from Qwen2.5-Coder:7b for code analysis and security audits."""
        async for token in self._call_ollama_stream(messages, model=settings.OLLAMA_MODEL_CODER):
            yield token

    async def _call_vision_stream(self, messages: List[Dict[str, str]], images: Optional[List[str]] = None) -> AsyncGenerator[str, None]:
        """Streams responses specifically from Qwen2.5-VL:3b for OCR, PDFs, screenshots and architectural diagrams."""
        async for token in self._call_ollama_stream(messages, model=settings.OLLAMA_MODEL_VISION, images=images):
            yield token

    async def _call_groq_stream(self, messages: List[Dict[str, str]], max_tokens: int = 2048) -> AsyncGenerator[str, None]:
        """Streams responses from Groq async - does NOT block the event loop."""
        if not self.groq_client:
            if self.gemini_client:
                async for token in self._call_gemini_stream(messages):
                    yield token
                return
            async for token in self._call_ollama_stream(messages):
                yield token
            return

        try:
            from groq import AsyncGroq
            async_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
            stream = await async_client.chat.completions.create(
                model=settings.GROQ_LLM_MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=max_tokens,
                stream=True
            )
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
        except Exception as e:
            logger.error(f"Groq async streaming error: {e}")
            try:
                from groq import AsyncGroq
                async_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                stream = await async_client.chat.completions.create(
                    model=settings.GROQ_FAST_MODEL,
                    messages=messages,
                    temperature=0.4,
                    max_tokens=max_tokens,
                    stream=True
                )
                async for chunk in stream:
                    content = chunk.choices[0].delta.content
                    if content:
                        yield content
            except Exception as e2:
                logger.error(f"Groq fast model fallback error: {e2}")
                async for token in self._offline_fallback_response(messages):
                    yield token

    async def _call_gemini_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Streams responses from Google Gemini using the official google-genai SDK."""
        if not self.gemini_client:
            if self.groq_client:
                async for token in self._call_groq_stream(messages):
                    yield token
                return
            async for token in self._call_ollama_stream(messages):
                yield token
            return

        try:
            from google.genai import types
            import asyncio

            # Extract system instruction and user contents
            system_instr = ""
            contents = []
            for m in messages:
                if m["role"] == "system":
                    system_instr += m["content"] + "\n"
                else:
                    role_str = "user" if m["role"] == "user" else "model"
                    contents.append(f"{role_str}: {m['content']}")

            full_prompt = "\n\n".join(contents)

            config = types.GenerateContentConfig(
                system_instruction=system_instr.strip() if system_instr else None,
                temperature=0.3,
                max_output_tokens=1024
            )

            loop = asyncio.get_event_loop()
            def _get_stream():
                return self.gemini_client.models.generate_content_stream(
                    model=settings.GEMINI_MODEL,
                    contents=full_prompt,
                    config=config
                )

            stream = await loop.run_in_executor(None, _get_stream)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0.01)

        except Exception as e:
            logger.warning(f"Gemini streaming failed: {e}, falling back to Groq / local.")
            if self.groq_client:
                async for token in self._call_groq_stream(messages):
                    yield token
            else:
                async for token in self._offline_fallback_response(messages):
                    yield token

    async def _offline_fallback_response(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """
        Smart autonomous offline handler when cloud API keys are not yet configured.
        Parses intent for tools, executes diagnostics, and responds conversationally to Abhishek.
        """
        last_user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user_msg = m["content"].lower().strip()
                break

        # Check for tool trigger intents
        if any(w in last_user_msg for w in ["cpu", "ram", "memory", "battery", "system info", "system stats", "hardware"]):
            tool_json = '```json\n{"tool": "get_system_info", "params": {}}\n```'
            for chunk in ["```json\n", '{"tool": "get_system_info", "params": {}}\n', "```"]:
                yield chunk
                await asyncio.sleep(0.05)
            return

        if "scan" in last_user_msg or "port" in last_user_msg:
            tool_json = '```json\n{"tool": "run_scanner", "params": {"target": "127.0.0.1", "ports": "80,443,8000,8080"}}\n```'
            for chunk in ["```json\n", '{"tool": "run_scanner", "params": {"target": "127.0.0.1", "ports": "80,443,8000,8080"}}\n', "```"]:
                yield chunk
                await asyncio.sleep(0.05)
            return

        if "cve" in last_user_msg or "vulnerability" in last_user_msg:
            tool_json = '```json\n{"tool": "cve_lookup", "params": {"keyword": "remote code execution"}}\n```'
            for chunk in ["```json\n", '{"tool": "cve_lookup", "params": {"keyword": "remote code execution"}}\n', "```"]:
                yield chunk
                await asyncio.sleep(0.05)
            return

        if any(app in last_user_msg for app in ["chrome", "spotify", "vscode", "notepad", "discord", "calculator", "calc"]):
            app_name = "notepad"
            for candidate in ["chrome", "spotify", "vscode", "notepad", "discord", "calculator", "calc"]:
                if candidate in last_user_msg:
                    app_name = candidate
                    break
            for chunk in ["```json\n", f'{{"tool": "launch_app", "params": {{"app_name": "{app_name}"}}}}\n', "```"]:
                yield chunk
                await asyncio.sleep(0.05)
            return

        # General conversational greeting & helper
        if any(g in last_user_msg for g in ["hello", "hi", "hey", "who are you", "what can you do"]):
            reply = (
                "Hello Abhishek! Chloe here, all local systems and MCP tools are active. "
                "To unlock frontier cloud intelligence, you can configure your Groq or Google Gemini API key in the top settings panel. "
                "Meanwhile, all system commands, port scanning, hardware telemetry, and app launchers are ready to execute on your command."
            )
        else:
            reply = (
                f"I hear you, Abhishek. I am operating on local standby mode. "
                f"You can command me to inspect system hardware, launch applications, scan ports, or configure your API keys in the settings menu to enable deep reasoning."
            )

        # Stream words smoothly
        for word in reply.split(" "):
            yield word + " "
            await asyncio.sleep(0.03)

    def _check_fast_path_command(self, user_text: str) -> Optional[tuple]:
        """
        Sub-millisecond NLP intent and entity extractor for OS & desktop directives.
        Returns (tool_name, params, natural_speech_confirmation) or None.
        """
        try:
            from app.core.nlp_engine import nlp_engine
            nlp_res = nlp_engine.parse(user_text)

            if nlp_res.tool_name and nlp_res.confidence >= 0.70:
                confirmation = nlp_res.instant_response or f"Executing {nlp_res.tool_name}."
                return (nlp_res.tool_name, nlp_res.tool_params or {}, confirmation)

            # Quick Math Calculation (zero tool needed, instant result)
            if nlp_res.intent == "QUICK_CALC" and nlp_res.instant_response:
                return ("_instant_nlp_reply", {"reply": nlp_res.instant_response}, nlp_res.instant_response)
        except Exception as e:
            logger.debug(f"NLP fast-path parse skipped: {e}")

        text = user_text.lower().strip().rstrip(".!?,")
        
        # 1. Launch App & Website Directives (fallback pattern matcher)
        app_patterns = [
            (r'^(?:chloe\s+)?(?:open|launch|start|run|explore|show)\s+(?:local\s+)?(?:disk|disc)\s+([a-zA-Z])$', "launch_app"),
            (r'^(?:chloe\s+)?(?:open|launch|start|run|explore|show)\s+(?:the\s+)?([a-zA-Z])(?:\s+drive|:)$', "launch_app"),
            (r'^(?:chloe\s+)?(?:open|launch|start|run|goto|visit)\s+([a-zA-Z0-9\.\-_:/]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)$', "launch_app"),
            (r'^(?:chloe\s+)?(?:open|launch|start|run)\s+(cmd|cmd\.exe|command\s+prompt|command|terminal|windows\s+terminal|wt|powershell|pwsh|notepad|notepad\.exe|chrome|google\s+chrome|browser|vscode|vs\s+code|code|calc|calculator|spotify|discord|explorer|file\s+explorer|files|task\s+manager|taskmgr|settings|github|youtube|gmail|google|reddit|twitter|chatgpt|whatsapp)$', "launch_app"),
            (r'^(?:chloe\s+)?(?:open|launch)\s+the\s+(cmd|command\s+prompt|terminal|notepad|chrome|calculator|task\s+manager|settings|explorer|whatsapp)$', "launch_app")
        ]
        for pattern, tool in app_patterns:
            m = re.match(pattern, text)
            if m:
                target_app = m.group(1).strip()
                if "." in target_app:
                    display_name = target_app
                elif len(target_app) <= 4:
                    display_name = target_app.upper()
                else:
                    display_name = target_app.title()
                return (tool, {"app_name": target_app}, f"Opening {display_name} for you.")

        # 2. Direct System Diagnostics
        if text in ["system status", "status", "chloe system status", "system info", "check status", "system diagnostics", "pc status"]:
            return ("get_system_info", {}, "Checking system telemetry now.")

        # 3. Direct Port Scanner
        if text.startswith("scan ports on ") or text.startswith("scan port "):
            target = text.split("on ")[-1].strip() if "on " in text else "127.0.0.1"
            return ("run_scanner", {"target": target, "ports": [80, 443, 8000, 8080, 11434]}, f"Scanning target {target}.")

        return None

    async def unload_ollama_models(self):
        """Unloads all Ollama models from RAM to immediately drop memory usage when in cloud mode."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                for model in [settings.OLLAMA_MODEL, settings.OLLAMA_MODEL_CODER, settings.OLLAMA_MODEL_VISION, settings.OLLAMA_MODEL_OFFLINE]:
                    try:
                        async with session.post(
                            f"{settings.OLLAMA_HOST}/api/generate",
                            json={"model": model, "keep_alive": 0},
                            timeout=1.0
                        ) as resp:
                            pass
                    except Exception:
                        pass
            logger.info("Orchestrator: Requested Ollama to unload resident models from RAM.")
        except Exception as e:
            logger.debug(f"Ollama unload skipped: {e}")

    async def process_interaction(
        self,
        session_id: str,
        user_text: str,
        mode: OperatingMode = OperatingMode.PARTIALLY_ISOLATED,
        speak: bool = True,
        voice: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Main Agentic Interaction Loop.
        Supports speak parameter to toggle Kokoro female voice synthesis.
        """
        # Standardize session ID so Abhishek's conversations maintain persistent context
        active_session = "session_abhishek" if (not session_id or session_id.startswith("session_")) else session_id
        mode_str = mode.value if hasattr(mode, "value") else str(mode)

        logger.info(f"Orchestrator: User [{active_session}] ({mode_str}, speak={speak}): '{user_text}'")
        db_storage.save_message(active_session, "user", user_text, mode_str)

        # 0. Zero-Latency NLP Intent Fast-Path (<1ms OS command & math execution)
        fast_cmd = self._check_fast_path_command(user_text)
        if fast_cmd:
            tool_name, params, confirmation_speech = fast_cmd
            logger.info(f"Orchestrator: NLP Fast-Path direct intercept '{tool_name}' with params {params}")
            
            if tool_name == "_instant_nlp_reply":
                for word in confirmation_speech.split(" "):
                    yield {"type": "token", "token": word + " "}
                    await asyncio.sleep(0.01)

                if speak:
                    audio_b64 = await tts_engine.synthesize_to_base64(confirmation_speech, voice=voice)
                    if audio_b64:
                        yield {"type": "sentence_audio", "sentence": confirmation_speech, "audio_base64": audio_b64}

                db_storage.save_message(active_session, "assistant", confirmation_speech, mode_str)
                try:
                    from app.core.memory_engine import memory_engine
                    asyncio.create_task(memory_engine.learn_from_interaction(
                        user_text=user_text,
                        assistant_response=confirmation_speech,
                        tool_executions=None,
                        session_id=active_session
                    ))
                except Exception:
                    pass
                yield {"type": "done"}
                return

            yield {
                "type": "tool_start",
                "tool": tool_name,
                "params": params
            }

            from app.mcp.dispatcher import mcp_dispatcher
            tool_result = await mcp_dispatcher.execute_tool(tool_name, params, mode)

            db_storage.log_tool_execution(
                session_id=active_session,
                tool_name=tool_name,
                params=params,
                status=tool_result.get("status", "unknown"),
                result=tool_result.get("result", {}),
                mode=mode_str
            )

            yield {
                "type": "tool_result",
                "tool": tool_name,
                "result": tool_result
            }

            # Stream fast conversational confirmation
            for word in confirmation_speech.split(" "):
                yield {"type": "token", "token": word + " "}
                await asyncio.sleep(0.01)

            if speak:
                audio_b64 = await tts_engine.synthesize_to_base64(confirmation_speech, voice=voice)
                if audio_b64:
                    yield {"type": "sentence_audio", "sentence": confirmation_speech, "audio_base64": audio_b64}

            db_storage.save_message(active_session, "assistant", confirmation_speech, mode_str)
            try:
                from app.core.memory_engine import memory_engine
                asyncio.create_task(memory_engine.learn_from_interaction(
                    user_text=user_text,
                    assistant_response=confirmation_speech,
                    tool_executions=[{"tool": tool_name, "params": params}],
                    session_id=active_session
                ))
            except Exception:
                pass
            yield {"type": "done"}
            return

        # 1. Automatic Semantic RAG Retrieval: always query ChromaDB if the knowledge vault contains indexed chunks
        rag_context = ""
        try:
            vault_stats = rag_pipeline.get_vault_stats()
            if vault_stats.get("total_chunks", 0) > 0:
                docs = await rag_pipeline.query_documents(user_text, top_k=3)
                if docs:
                    rag_context = "\n".join([f"- [Source: {d.get('source')}]: {d.get('content')}" for d in docs])
                    logger.info(f"Orchestrator: Injected {len(docs)} ChromaDB chunks into context across {mode_str}.")
        except Exception as e:
            logger.warning(f"RAG semantic query skipped: {e}")

        # 2. Retrieve Continuous Learning Context (Level 1: Memories & Level 2: Action Experiences)
        learned_memory_context = ""
        experience_context = ""
        try:
            from app.core.memory_engine import memory_engine
            learned_mems = memory_engine.retrieve_relevant_memories(user_text, top_k=4)
            if learned_mems:
                learned_memory_context = "\n".join([f"- {m}" for m in learned_mems])
                logger.info(f"Orchestrator: Injected {len(learned_mems)} learned memories into prompt.")

            exps = memory_engine.retrieve_relevant_experiences(user_text, top_k=2)
            if exps:
                experience_context = "\n".join([f"- Similar Goal '{e['user_intent']}': {json.dumps(e['tool_sequence'])}" for e in exps])
                logger.info(f"Orchestrator: Injected {len(exps)} action skill experiences into prompt.")
        except Exception as e:
            logger.warning(f"Memory retrieval skipped: {e}")

        # 3. Process via LangGraph Unified Persona & Tri-Mode Router with Full History
        recent_history = db_storage.get_recent_messages(active_session, limit=14)
        history_msgs = [{"role": h["role"], "content": h["content"]} for h in recent_history[:-1]]
        
        graph_state = chloe_langgraph_router.process_route(
            session_id=active_session,
            user_text=user_text,
            mode=mode.value,
            rag_context=rag_context,
            learned_memory_context=learned_memory_context,
            experience_context=experience_context,
            speak=speak,
            history_messages=history_msgs
        )
        messages = graph_state["messages"]
        target_engine = graph_state["target_engine"]
        selected_model = graph_state.get("selected_model", settings.OLLAMA_MODEL)

        # Notify Web HUD of active executing model & engine in real-time
        yield {
            "type": "model_info",
            "model": selected_model,
            "engine": target_engine,
            "mode": mode_str
        }

        # 3. Stream from Targeted Engine
        if target_engine == "ollama_coder":
            token_stream = self._call_coder_stream(messages)
        elif target_engine == "ollama_vision":
            token_stream = self._call_vision_stream(messages)
        elif target_engine == "ollama_offline":
            token_stream = self._call_ollama_stream(messages, model=settings.OLLAMA_MODEL_OFFLINE)
        elif target_engine == "ollama_primary":
            token_stream = self._call_ollama_stream(messages, model=settings.OLLAMA_MODEL)
        elif target_engine == "gemini":
            token_stream = self._call_gemini_stream(messages)
        else:
            token_stream = self._call_groq_stream(messages)

        # 4. Stream Tokens & Buffer Sentences
        full_completion = ""
        stream_buffer = SentenceStreamBuffer()

        async for event in self._stream_clean_response(token_stream, stream_buffer, speak, voice):
            if event["type"] == "token":
                full_completion += event["token"]
            yield event

        # 5. Check for MCP Tool Calls
        tool_calls = stream_buffer.extract_tool_calls(full_completion)
        if tool_calls:
            tool_findings = []
            from app.mcp.dispatcher import mcp_dispatcher

            for call in tool_calls:
                tool_name = call.get("tool") or call.get("action")
                params = call.get("params", {})
                
                yield {
                    "type": "tool_start",
                    "tool": tool_name,
                    "params": params
                }

                tool_result = await mcp_dispatcher.execute_tool(tool_name, params, mode)
                
                db_storage.log_tool_execution(
                    session_id=active_session,
                    tool_name=tool_name,
                    params=params,
                    status=tool_result.get("status", "unknown"),
                    result=tool_result.get("result", {}),
                    mode=mode_str
                )

                yield {
                    "type": "tool_result",
                    "tool": tool_name,
                    "result": tool_result
                }

                tool_findings.append({
                    "tool": tool_name,
                    "params": params,
                    "result": tool_result
                })

            follow_up_messages = list(messages)
            follow_up_messages.append({"role": "assistant", "content": full_completion})
            follow_up_messages.append({
                "role": "system",
                "content": f"ALL TOOL EXECUTION FINDINGS:\n{json.dumps(tool_findings, indent=2)}\n\nIf you have any remaining tasks (such as writing files into newly created folders), execute the remaining tool now. Otherwise, confirm completion succinctly and naturally for Abhishek in voice conversation. Do NOT output raw think tags."
            })

            if mode_str == OperatingMode.FULLY_ISOLATED.value:
                summary_stream = self._call_ollama_stream(follow_up_messages)
            elif mode_str == OperatingMode.COMPLETELY_OPEN.value:
                summary_stream = self._call_gemini_stream(follow_up_messages)
            else:
                summary_stream = self._call_groq_stream(follow_up_messages)

            summary_buffer = SentenceStreamBuffer()
            summary_full = ""

            async for s_event in self._stream_clean_response(summary_stream, summary_buffer, speak, voice):
                if s_event["type"] == "token":
                    summary_full += s_event["token"]
                yield s_event

            # Check if summary produced a secondary tool call (e.g. write_file after create_folder)
            secondary_tool_calls = summary_buffer.extract_tool_calls(summary_full)
            if secondary_tool_calls:
                for sec_call in secondary_tool_calls:
                    sec_tool_name = sec_call.get("tool") or sec_call.get("action")
                    sec_params = sec_call.get("params", {})
                    yield {
                        "type": "tool_start",
                        "tool": sec_tool_name,
                        "params": sec_params
                    }
                    sec_res = await mcp_dispatcher.execute_tool(sec_tool_name, sec_params, mode)
                    db_storage.log_tool_execution(
                        session_id=active_session,
                        tool_name=sec_tool_name,
                        params=sec_params,
                        status=sec_res.get("status", "unknown"),
                        result=sec_res.get("result", {}),
                        mode=mode_str
                    )
                    yield {
                        "type": "tool_result",
                        "tool": sec_tool_name,
                        "result": sec_res
                    }

            db_storage.save_message(active_session, "assistant", summary_full, mode_str)
            try:
                from app.core.memory_engine import memory_engine
                combined_tools = tool_calls + (secondary_tool_calls or [])
                asyncio.create_task(memory_engine.learn_from_interaction(
                    user_text=user_text,
                    assistant_response=summary_full,
                    tool_executions=combined_tools,
                    session_id=active_session
                ))
            except Exception:
                pass
            yield {"type": "done"}
            return

        db_storage.save_message(active_session, "assistant", full_completion, mode_str)
        try:
            from app.core.memory_engine import memory_engine
            asyncio.create_task(memory_engine.learn_from_interaction(
                user_text=user_text,
                assistant_response=full_completion,
                tool_executions=None,
                session_id=active_session
            ))
        except Exception:
            pass
        yield {"type": "done"}

    async def _stream_clean_response(self, token_stream, stream_buffer: SentenceStreamBuffer, speak: bool, voice: Optional[str] = None) -> AsyncGenerator[dict, None]:
        """
        Processes token stream, suppresses all <think>...</think> reasoning blocks,
        and yields clean tokens for UI and audio chunks for TTS.
        """
        in_think = False

        async for token in token_stream:
            # Handle <think> open
            if "<think>" in token:
                in_think = True
                prefix = token.split("<think>", 1)[0]
                if prefix:
                    yield {"type": "token", "token": prefix}
                    async for sentence in stream_buffer.process_token(prefix):
                        if speak:
                            audio_b64 = await tts_engine.synthesize_to_base64(sentence, voice=voice)
                            yield {"type": "sentence_audio", "sentence": sentence, "audio_base64": audio_b64}
                if "</think>" in token:
                    in_think = False
                    suffix = token.split("</think>", 1)[1]
                    if suffix:
                        yield {"type": "token", "token": suffix}
                        async for sentence in stream_buffer.process_token(suffix):
                            if speak:
                                audio_b64 = await tts_engine.synthesize_to_base64(sentence, voice=voice)
                                yield {"type": "sentence_audio", "sentence": sentence, "audio_base64": audio_b64}
                continue

            # Handle <think> close
            if in_think:
                if "</think>" in token:
                    in_think = False
                    suffix = token.split("</think>", 1)[1]
                    if suffix:
                        yield {"type": "token", "token": suffix}
                        async for sentence in stream_buffer.process_token(suffix):
                            if speak:
                                audio_b64 = await tts_engine.synthesize_to_base64(sentence, voice=voice)
                                yield {"type": "sentence_audio", "sentence": sentence, "audio_base64": audio_b64}
                continue

            # Yield clean text token immediately to screen UI
            yield {"type": "token", "token": token}

            async for sentence in stream_buffer.process_token(token):
                if speak:
                    audio_b64 = await tts_engine.synthesize_to_base64(sentence, voice=voice)
                    yield {"type": "sentence_audio", "sentence": sentence, "audio_base64": audio_b64}

        async for remaining_sentence in stream_buffer.flush():
            if speak:
                audio_b64 = await tts_engine.synthesize_to_base64(remaining_sentence, voice=voice)
                yield {"type": "sentence_audio", "sentence": remaining_sentence, "audio_base64": audio_b64}

orchestrator = ChloeOrchestrator()
