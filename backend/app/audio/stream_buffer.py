"""
Project Chloe - SentenceStreamBuffer
Splits incoming LLM token stream into natural sentence boundaries (. , ! ? \n)
so TTS synthesis begins immediately without waiting for the full LLM completion.
Strictly suppresses TTS synthesis for JSON tool blocks, code fences, and symbols.
"""

import re
import json
import asyncio
from typing import AsyncGenerator, Callable, Optional, List

class SentenceStreamBuffer:
    def __init__(self, on_sentence_ready: Optional[Callable[[str], None]] = None):
        self.buffer = ""
        self.full_response = ""
        self.on_sentence_ready = on_sentence_ready
        self.punct_regex = re.compile(r'([.!?\n;:]+)')
        self.clause_comma_regex = re.compile(r'(,\s+)')
        self.in_tool_block = False
        self.in_think_block = False
        self.first_sentence_sent = False

    def is_tool_call_start(self, text: str) -> bool:
        """Detects if the text indicates the start of a tool JSON call or markdown code block."""
        stripped = text.strip()
        return (
            stripped.startswith('{') or 
            stripped.startswith('```') or
            '"tool":' in stripped or
            '"action":' in stripped or
            '"params":' in stripped
        )

    def extract_tool_calls(self, text: str) -> List[dict]:
        """Extracts JSON tool call objects from the generated response across multiple format standards."""
        cleaned_text = re.sub(r'<think>[\s\S]*?</think>', '', text)
        tool_calls = []
        
        # 1. Match markdown json blocks
        json_matches = re.findall(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', cleaned_text)
        for match in json_matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict):
                    tool_name = parsed.get("tool") or parsed.get("action") or parsed.get("name")
                    if tool_name:
                        params = parsed.get("params") or parsed.get("arguments") or parsed.get("parameters") or {}
                        if isinstance(params, str):
                            try:
                                params = json.loads(params)
                            except Exception:
                                pass
                        tool_calls.append({"tool": tool_name, "params": params})
            except Exception:
                pass

        if tool_calls:
            return tool_calls

        # 2. Balanced brace scanner for standalone JSON objects
        start_idx = -1
        depth = 0
        for i, char in enumerate(cleaned_text):
            if char == '{':
                if depth == 0:
                    start_idx = i
                depth += 1
            elif char == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx != -1:
                        json_str = cleaned_text[start_idx:i+1]
                        try:
                            parsed = json.loads(json_str)
                            if isinstance(parsed, dict):
                                tool_name = parsed.get("tool") or parsed.get("action") or parsed.get("name")
                                if tool_name:
                                    params = parsed.get("params") or parsed.get("arguments") or parsed.get("parameters") or {}
                                    if isinstance(params, str):
                                        try:
                                            params = json.loads(params)
                                        except Exception:
                                            pass
                                    tool_calls.append({"tool": tool_name, "params": params})
                        except Exception:
                            pass
                        start_idx = -1

        return tool_calls

    async def process_token(self, token: str) -> AsyncGenerator[str, None]:
        """
        Receives a single LLM token, appends to buffer, and yields complete sentences/clauses immediately for sub-1s TTFA.
        """
        self.full_response += token

        # Handle <think> reasoning tokens suppression for clean voice
        if "<think>" in token:
            self.in_think_block = True
            if "</think>" in token:
                self.in_think_block = False
                token = token.split("</think>", 1)[1]
            else:
                return

        if self.in_think_block:
            if "</think>" in token:
                self.in_think_block = False
                token = token.split("</think>", 1)[1]
                self.buffer = ""
            else:
                return

        if not token:
            return

        self.buffer += token

        # Check for tool call directive or code block
        if not self.in_tool_block and self.is_tool_call_start(self.buffer):
            self.in_tool_block = True

        if self.in_tool_block:
            # Check if tool block has closed
            if self.buffer.count('{') > 0 and self.buffer.count('{') == self.buffer.count('}'):
                self.in_tool_block = False
                self.buffer = ""
            return

        # Split on standard sentence boundaries (. ! ? \n)
        parts = self.punct_regex.split(self.buffer)
        if len(parts) > 1:
            complete_sentence = ""
            for i in range(0, len(parts) - 1, 2):
                complete_sentence += parts[i] + parts[i+1]
            
            self.buffer = parts[-1]
            
            clean_sentence = self._sanitize_for_speech(complete_sentence)
            if clean_sentence and len(clean_sentence.split()) >= 2:
                self.first_sentence_sent = True
                if self.on_sentence_ready:
                    if asyncio.iscoroutinefunction(self.on_sentence_ready):
                        await self.on_sentence_ready(clean_sentence)
                    else:
                        self.on_sentence_ready(clean_sentence)
                yield clean_sentence
        else:
            # Fallback for long continuous stream without punctuation (>= 15 words)
            words = self.buffer.strip().split()
            if len(words) >= 15:
                chunk = " ".join(words[:12])
                self.buffer = " ".join(words[12:])
                clean_chunk = self._sanitize_for_speech(chunk)
                if clean_chunk:
                    self.first_sentence_sent = True
                    if self.on_sentence_ready:
                        if asyncio.iscoroutinefunction(self.on_sentence_ready):
                            await self.on_sentence_ready(clean_chunk)
                        else:
                            self.on_sentence_ready(clean_chunk)
                    yield clean_chunk

    def _sanitize_for_speech(self, text: str) -> str:
        """Removes code markers, JSON braces, and requires alphanumeric content."""
        cleaned = re.sub(r'```[\s\S]*?```', '', text)
        cleaned = re.sub(r'[\{\}\[\]\<\>\*_~`]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if len(re.findall(r'[a-zA-Z0-9]', cleaned)) < 2:
            return ""
        return cleaned

    async def flush(self) -> AsyncGenerator[str, None]:
        """
        Flushes any remaining text in the buffer at the end of the LLM stream.
        """
        if not self.in_tool_block:
            remaining = self._sanitize_for_speech(self.buffer)
            if remaining and len(remaining.split()) >= 1:
                if self.on_sentence_ready:
                    if asyncio.iscoroutinefunction(self.on_sentence_ready):
                        await self.on_sentence_ready(remaining)
                    else:
                        self.on_sentence_ready(remaining)
                yield remaining
        self.buffer = ""
