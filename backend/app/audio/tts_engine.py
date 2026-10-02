"""
Project Chloe - 4-Tier Text-to-Speech (TTS) Waterfall Engine
1. Microsoft Edge-TTS (Online Neural: en-US-AriaNeural, en-GB-SoniaNeural)
2. Local Kokoro-82M ONNX
3. Ollama Kokoro TTS Endpoint
4. pyttsx3 / Windows SAPI5 (Offline Failsafe)
"""

import io
import os
import re
import logging
import asyncio
import base64
from typing import AsyncGenerator, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class TTSEngine:
    def __init__(self):
        self.default_voice = settings.DEFAULT_TTS_VOICE
        self.fallback_voice = settings.TTS_FALLBACK_VOICE
        self._init_pyttsx3()

    def _init_pyttsx3(self):
        """Initialize offline pyttsx3 SAPI5 fallback engine."""
        self.pyttsx3_engine = None
        try:
            import pyttsx3
            self.pyttsx3_engine = pyttsx3.init()
            # Set speech rate and preferred female voice
            self.pyttsx3_engine.setProperty('rate', 175)
            voices = self.pyttsx3_engine.getProperty('voices')
            for voice in voices:
                if "zira" in voice.name.lower() or "hazel" in voice.name.lower() or "female" in voice.name.lower():
                    self.pyttsx3_engine.setProperty('voice', voice.id)
                    break
        except Exception as e:
            logger.warning(f"TTSEngine: Failed to initialize pyttsx3: {e}")

    def clean_text_for_speech(self, text: str) -> str:
        """Strip markdown markers, code blocks, URLs, and JSON for clear spoken audio."""
        if not text:
            return ""
        
        # Remove markdown code blocks ```...```
        text = re.sub(r"```[\s\S]*?```", "Code block omitted.", text)
        # Remove inline code `...`
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove URLs
        text = re.sub(r"https?://\S+", "link", text)
        # Remove markdown bold/italics
        text = re.sub(r"[\*_#~]", "", text)
        # Remove markdown table formatting
        text = re.sub(r"\|", " ", text)
        # Remove JSON-like brackets
        text = re.sub(r"\{.*?\}", "", text)
        # Clean extra whitespaces
        text = re.sub(r"\s+", " ", text).strip()
        return text

    async def synthesize_with_edge_tts(self, text: str, voice: Optional[str] = None) -> bytes:
        """Synthesizes text using Microsoft Edge-TTS."""
        import edge_tts
        chosen_voice = voice or self.default_voice
        communicate = edge_tts.Communicate(
            text=text,
            voice=chosen_voice,
            rate=settings.TTS_RATE,
            pitch=settings.TTS_PITCH
        )
        audio_buffer = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.extend(chunk["data"])
        return bytes(audio_buffer)

    def synthesize_with_pyttsx3(self, text: str) -> bytes:
        """Synthesizes text using offline pyttsx3 and returns WAV bytes."""
        import tempfile
        import wave
        if not self.pyttsx3_engine:
            return b""
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = tmp.name
            
        try:
            self.pyttsx3_engine.save_to_file(text, tmp_path)
            self.pyttsx3_engine.runAndWait()
            with open(tmp_path, "rb") as f:
                data = f.read()
            return data
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    async def synthesize_to_bytes(self, text: str, voice: Optional[str] = None) -> bytes:
        """
        Synthesizes speech with direct user voice/engine selection:
        - "edge:<voice_id>" -> Microsoft Edge Neural Cloud
        - "kokoro:<voice_id>" -> In-Memory Kokoro-82M ONNX (e.g. af_bella, af_sarah, am_adam, bf_emma)
        - "sapi5:..." -> Windows Native SAPI5
        - None / Default -> Waterfall fallback (Edge Aria -> Kokoro Bella -> pyttsx3)
        """
        clean_text = self.clean_text_for_speech(text)
        if not clean_text or len(clean_text.strip()) == 0:
            return b""

        # 1. Direct Kokoro-82M Selection
        if voice and voice.startswith("kokoro:"):
            kokoro_voice = voice.split("kokoro:")[1].strip() or "af_bella"
            if os.path.exists(settings.KOKORO_ONNX_PATH) and os.path.exists(settings.KOKORO_VOICES_PATH):
                try:
                    loop = asyncio.get_event_loop()
                    audio_bytes = await loop.run_in_executor(None, self.synthesize_with_kokoro_onnx, clean_text, kokoro_voice)
                    if audio_bytes and len(audio_bytes) > 200:
                        return audio_bytes
                except Exception as e:
                    logger.warning(f"TTSEngine: Direct Kokoro ({kokoro_voice}) failed: {e}")

        # 2. Direct Edge-TTS Selection
        elif voice and voice.startswith("edge:"):
            edge_voice = voice.split("edge:")[1].strip() or self.default_voice
            try:
                audio_bytes = await asyncio.wait_for(self.synthesize_with_edge_tts(clean_text, voice=edge_voice), timeout=3.5)
                if audio_bytes and len(audio_bytes) > 200:
                    return audio_bytes
            except Exception as e:
                logger.warning(f"TTSEngine: Direct Edge-TTS ({edge_voice}) failed: {e}")

        # 3. Direct SAPI5 Selection
        elif voice and voice.startswith("sapi5"):
            try:
                loop = asyncio.get_event_loop()
                audio_bytes = await loop.run_in_executor(None, self.synthesize_with_pyttsx3, clean_text)
                if audio_bytes and len(audio_bytes) > 200:
                    return audio_bytes
            except Exception as e:
                logger.warning(f"TTSEngine: Direct SAPI5 failed: {e}")

        # 4. Default Waterfall Fallback:
        # Tier 1: Microsoft Edge-TTS
        try:
            audio_bytes = await asyncio.wait_for(self.synthesize_with_edge_tts(clean_text), timeout=2.5)
            if audio_bytes and len(audio_bytes) > 200:
                return audio_bytes
        except Exception as e:
            logger.warning(f"TTSEngine: Edge-TTS waterfall skipped/failed: {e}")

        # Tier 2: In-Memory Kokoro-82M ONNX
        if os.path.exists(settings.KOKORO_ONNX_PATH) and os.path.exists(settings.KOKORO_VOICES_PATH):
            try:
                loop = asyncio.get_event_loop()
                audio_bytes = await loop.run_in_executor(None, self.synthesize_with_kokoro_onnx, clean_text, "af_bella")
                if audio_bytes and len(audio_bytes) > 200:
                    return audio_bytes
            except Exception as e:
                logger.warning(f"TTSEngine: Kokoro ONNX waterfall failed: {e}")

        # Tier 3: Native SAPI5 Engine
        try:
            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, self.synthesize_with_pyttsx3, clean_text)
            if audio_bytes and len(audio_bytes) > 200:
                return audio_bytes
        except Exception as e:
            logger.warning(f"TTSEngine: pyttsx3 SAPI5 failed: {e}")

        return b""

    def _get_kokoro(self):
        """Lazy load and cache the Kokoro-82M ONNX model in RAM once."""
        if not hasattr(self, "_kokoro_instance") or self._kokoro_instance is None:
            try:
                from kokoro_onnx import Kokoro
                self._kokoro_instance = Kokoro(settings.KOKORO_ONNX_PATH, settings.KOKORO_VOICES_PATH)
                logger.info("TTSEngine: Kokoro-82M ONNX neural model loaded into RAM.")
            except Exception as e:
                logger.warning(f"TTSEngine: Failed to load Kokoro ONNX: {e}")
                self._kokoro_instance = None
        return self._kokoro_instance

    def synthesize_with_kokoro_onnx(self, text: str, voice: str = "af_bella") -> bytes:
        """Synthesizes text using cached in-memory Kokoro-82M ONNX engine."""
        try:
            import soundfile as sf
            kokoro = self._get_kokoro()
            if not kokoro:
                return b""
            
            # Use native speed 1.0 without distortion
            samples, sample_rate = kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
            
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format='WAV')
            return buf.getvalue()
        except Exception as e:
            logger.warning(f"Kokoro ONNX ({voice}) execution error: {e}")
            return b""

    async def synthesize_to_base64(self, text: str, voice: Optional[str] = None) -> str:
        """Returns base64 encoded audio string ready for WebSocket transport."""
        audio_bytes = await self.synthesize_to_bytes(text, voice=voice)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode("utf-8")
        return ""

tts_engine = TTSEngine()
