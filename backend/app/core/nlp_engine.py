"""
Project Chloe - Fast NLP Intent, Entity Extraction & Phonetic Auto-Correction Engine
Sub-millisecond rule-based and phonetic slot filling, speech transcript auto-correction,
contextual reference resolution ('open this'), file creation, and named entity recognition.
"""

import os
import re
import math
import logging
import difflib
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("ChloeNLP")

# Standard Known Windows App Aliases Mapping
KNOWN_APP_MAP = {
    # Code & Development
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "visual studio": "devenv",
    "pycharm": "pycharm64",
    "git bash": "git-bash",
    "terminal": "wt",
    "windows terminal": "wt",
    "powershell": "powershell",
    "cmd": "cmd",
    "command prompt": "cmd",

    # Browsers & Internet
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "brave": "brave",
    "opera": "opera",

    # Communication & Social
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",

    # Productivity & Office
    "notepad": "notepad",
    "notepad++": "notepad++",
    "calculator": "calc",
    "calc": "calc",
    "word": "winword",
    "ms word": "winword",
    "excel": "excel",
    "ms excel": "excel",
    "powerpoint": "powerpnt",
    "ms powerpoint": "powerpnt",

    # System Utilities
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "file explorer": "explorer",
    "explorer": "explorer",
    "my computer": "explorer",
    "this pc": "explorer",
    "control panel": "control",
    "settings": "ms-settings:",
    "paint": "mspaint",
    "snipping tool": "snippingtool",

    # Media & Entertainment
    "spotify": "spotify",
    "vlc": "vlc",
    "steam": "steam",
    "obs": "obs64"
}

# Standard Windows Directory Shortcuts
KNOWN_DIR_MAP = {
    "desktop": str(Path.home() / "Desktop"),
    "downloads": str(Path.home() / "Downloads"),
    "documents": str(Path.home() / "Documents"),
    "my documents": str(Path.home() / "Documents"),
    "pictures": str(Path.home() / "Pictures"),
    "music": str(Path.home() / "Music"),
    "videos": str(Path.home() / "Videos"),
    "home": str(Path.home()),
    "user folder": str(Path.home()),
    "c drive": "C:\\",
    "drive c": "C:\\",
    "local disk c": "C:\\",
    "disk c": "C:\\",
    "d drive": "D:\\",
    "drive d": "D:\\",
    "local disk d": "D:\\",
    "disk d": "D:\\",
    "e drive": "E:\\",
    "drive e": "E:\\",
    "local disk e": "E:\\",
    "disk e": "E:\\",
    "f drive": "F:\\",
    "drive f": "F:\\",
    "local disk f": "F:\\",
    "disk f": "F:\\"
}

# High-Frequency Phonetic STT Mishearing Correction Patterns
PHONETIC_VOICE_RULES = [
    # Disk / Drive mishearings (e.g., "local disc the", "disk dee", "local dis d")
    (r"\b(?:local\s+)?(?:disk|disc|dis|dik|dex)\s+(?:the|dee|de|d)\b", "local disk D"),
    (r"\b(?:local\s+)?(?:disk|disc|dis|dik|dex)\s+(?:ee|e)\b", "local disk E"),
    (r"\b(?:local\s+)?(?:disk|disc|dis|dik|dex)\s+(?:sea|see|c)\b", "local disk C"),
    (r"\b(?:local\s+)?(?:disk|disc|dis|dik|dex)\s+([a-zA-Z])\b", r"local disk \1"),
    (r"\b(?:the|dee|de)\s+drive\b", "D drive"),
    (r"\bopen\s+(?:the\s+)?(?:d|dee|the)\s+drive\b", "open local disk D"),

    # VS Code mishearings (e.g. "vscod", "vs cold", "vis code")
    (r"\b(?:vs\s*cod|vis\s*code|visual\s*studio\s*cod|vs\s*cold|vscod|vs-code)\b", "vscode"),

    # WhatsApp mishearings
    (r"\b(?:whats\s*app|watsapp|whatapp|wat\s*sap|what\s*sap|what\s*sup)\b", "whatsapp"),

    # Google Chrome mishearings
    (r"\b(?:chrom|crome|google\s+chrom|google\s+crome)\b", "chrome"),

    # Notepad mishearings
    (r"\b(?:not\s*pad|note\s*pd|notepd|note-pad)\b", "notepad"),

    # Task Manager mishearings
    (r"\b(?:task\s*mngr|task\s*mangr|tast\s*manager|tas\s*manager|task\s*man)\b", "task manager"),

    # Calculator mishearings
    (r"\b(?:calculater|calcy|calcu|calculatr)\b", "calculator"),

    # Spotify mishearings
    (r"\b(?:spotfy|spoty|spotifi|spotif)\b", "spotify"),

    # PowerPoint mishearings
    (r"\b(?:powe\s*point|power\s*poit|power\s*pnt|powerpnt)\b", "powerpoint"),

    # Workstation Lock mishearings
    (r"\b(?:lok\s+pc|loc\s+pc|lock\s+work\s+station|lok\s+workstation|lock\s+windows\s+screen)\b", "lock workstation"),

    # Terminal / CMD mishearings
    (r"\b(?:terminl|termial|commad\s+prompt|cmd\s+promt)\b", "terminal"),

    # Downloads folder mishearings
    (r"\b(?:down\s*loads|down\s*load)\s+(?:folder|directory)?\b", "downloads folder")
]

TARGET_VOCABULARY = list(KNOWN_APP_MAP.keys()) + [
    "youtube", "github", "google", "downloads", "desktop", "documents", "calculator", "terminal"
]


@dataclass
class NLPEntityResult:
    intent: str
    confidence: float
    entities: Dict[str, Any] = field(default_factory=dict)
    action_suggested: Optional[str] = None
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    instant_response: Optional[str] = None
    normalized_text: str = ""
    corrected_transcript: str = ""


class NLPEngine:
    """
    Sub-millisecond Intent Classifier, Phonetic Auto-Corrector & Entity Extraction Engine.
    Executes in <0.5ms with zero cloud overhead.
    """

    def __init__(self):
        self.app_map = KNOWN_APP_MAP
        self.dir_map = KNOWN_DIR_MAP
        self.phonetic_rules = [(re.compile(pat, re.IGNORECASE), repl) for pat, repl in PHONETIC_VOICE_RULES]
        self.vocab = TARGET_VOCABULARY

    def correct_phonetics(self, text: str) -> str:
        """
        Fix speech recognition mishearings and phonetic typos in real-time.
        """
        if not text:
            return ""

        corrected = text.strip()

        # 1. Apply phonetic regex transformations
        for pattern, replacement in self.phonetic_rules:
            corrected = pattern.sub(replacement, corrected)

        # 2. Fuzzy token spelling auto-correction for target vocabulary
        words = corrected.split()
        fixed_words = []
        for w in words:
            clean_w = w.lower().strip(".,!?;:")
            if len(clean_w) >= 4 and clean_w not in self.vocab:
                matches = difflib.get_close_matches(clean_w, self.vocab, n=1, cutoff=0.82)
                if matches:
                    fixed_words.append(matches[0])
                    continue
            fixed_words.append(w)

        return " ".join(fixed_words)

    def normalize(self, text: str) -> str:
        """Clean, auto-correct phonetics, and normalize transcript text."""
        if not text:
            return ""
        phonetic_fixed = self.correct_phonetics(text)
        cleaned = phonetic_fixed.strip().lower()
        cleaned = re.sub(r'[?!.,;:]+$', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned

    def parse(self, text: str) -> NLPEntityResult:
        """
        Analyze input text, extract intents and entities with phonetic auto-correction.
        Returns NLPEntityResult with classified slots and suggested execution params.
        """
        raw = self.normalize(text)
        if not raw:
            return NLPEntityResult(intent="EMPTY", confidence=1.0, normalized_text="", corrected_transcript="")

        # 1. Contextual Reference Resolution (e.g. 'can you open this', 'open this', 'show me this', 'open it', 'open the file')
        if any(raw == phrase or raw.startswith(phrase) for phrase in [
            "can you open this", "can u open this", "open this", "open it", "launch this", 
            "show me this", "show this", "open the file", "open the website", "open the project", "run this", "execute this"
        ]):
            try:
                from app.db.storage import db_storage
                last_file = db_storage.get_last_created_file()
                if last_file:
                    return NLPEntityResult(
                        intent="OPEN_PATH",
                        confidence=0.98,
                        entities={"target_path": last_file, "context": "last_created_file"},
                        tool_name="launch_app",
                        tool_params={"app_name": last_file},
                        instant_response=f"Opening {os.path.basename(last_file)} for you.",
                        normalized_text=raw,
                        corrected_transcript=raw
                    )
            except Exception:
                pass

        # 2. Direct File Creation & Writing Intent (e.g. 'create a file notes.txt with text meeting at 5', 'write hello to file test.py')
        file_res = self._extract_file_write_intent(text)
        if file_res:
            file_res.corrected_transcript = raw
            return file_res

        # 3. Drive & Directory Explorations (e.g. 'open local disk D', 'open downloads folder')
        dir_res = self._extract_drive_or_path_intent(raw)
        if dir_res:
            dir_res.corrected_transcript = raw
            return dir_res

        # 4. System Lock & Workstation Controls
        sys_res = self._extract_system_control_intent(raw)
        if sys_res:
            sys_res.corrected_transcript = raw
            return sys_res

        # 5. Fast Safe Arithmetic Calculation (e.g. 'calculate 45 * 12', 'what is 20 percent of 500')
        calc_res = self._extract_math_intent(raw)
        if calc_res:
            calc_res.corrected_transcript = raw
            return calc_res

        # 6. App Launch Intent (e.g. 'open vs code', 'launch notepad', 'start chrome')
        app_res = self._extract_app_launch_intent(raw)
        if app_res:
            app_res.corrected_transcript = raw
            return app_res

        # 7. Web Search Intent (e.g. 'search google for fast whisper', 'search youtube for lofi music')
        search_res = self._extract_web_search_intent(raw)
        if search_res:
            search_res.corrected_transcript = raw
            return search_res

        # 8. Fallback: General Query for Frontier/Local LLM
        return NLPEntityResult(
            intent="GENERAL_QUERY",
            confidence=0.5,
            entities={"raw_query": text},
            normalized_text=raw,
            corrected_transcript=raw
        )

    def _extract_file_write_intent(self, text: str) -> Optional[NLPEntityResult]:
        """
        Extract direct file creation and writing directives.
        """
        p1 = r'^(?:create|make|write)\s+(?:a\s+)?(?:new\s+)?(?:python|text|markdown|code|json|csv)?\s*file\s+(?:named\s+|called\s+)?([a-zA-Z0-9_\-\.\:\\]+)(?:\s+(?:on|in)\s+([a-zA-Z0-9_\-\.\:\s\\]+?))?\s+(?:with\s+(?:the\s+)?(?:content|code|text|data)?\s*[:\s]?\s*|and\s+write\s+)(.+)$'
        m1 = re.match(p1, text, re.IGNORECASE)
        if m1:
            filename = m1.group(1).strip()
            location = m1.group(2).strip() if m1.group(2) else None
            content = m1.group(3).strip()

            target_path = self._resolve_target_file_path(filename, location)
            return NLPEntityResult(
                intent="CREATE_FILE",
                confidence=0.96,
                entities={"filename": filename, "path": target_path, "content": content},
                tool_name="write_file",
                tool_params={"path": target_path, "content": content},
                instant_response=f"Created file {os.path.basename(target_path)} with your content.",
                normalized_text=text
            )

        p2 = r'^write\s+(?:the\s+(?:text|content|code)\s+)?["\']?(.+?)["\']?\s+(?:in|to|into)\s+(?:file\s+)?([a-zA-Z0-9_\-\.\:\\]+)$'
        m2 = re.match(p2, text, re.IGNORECASE)
        if m2:
            content = m2.group(1).strip()
            filename = m2.group(2).strip()
            target_path = self._resolve_target_file_path(filename, None)
            return NLPEntityResult(
                intent="CREATE_FILE",
                confidence=0.94,
                entities={"filename": filename, "path": target_path, "content": content},
                tool_name="write_file",
                tool_params={"path": target_path, "content": content},
                instant_response=f"Written content to {os.path.basename(target_path)}.",
                normalized_text=text
            )

        p3 = r'^(?:create|make)\s+(?:a\s+)?(?:new\s+)?file\s+(?:named\s+|called\s+)?([a-zA-Z0-9_\-\.\:\\]+)$'
        m3 = re.match(p3, text, re.IGNORECASE)
        if m3:
            filename = m3.group(1).strip()
            if "." in filename:
                target_path = self._resolve_target_file_path(filename, None)
                return NLPEntityResult(
                    intent="CREATE_FILE",
                    confidence=0.90,
                    entities={"filename": filename, "path": target_path, "content": ""},
                    tool_name="write_file",
                    tool_params={"path": target_path, "content": ""},
                    instant_response=f"Created new file {os.path.basename(target_path)}.",
                    normalized_text=text
                )

        return None

    def _resolve_target_file_path(self, filename: str, location: Optional[str] = None) -> str:
        """Resolve a safe, clean target path on Windows."""
        if len(filename) >= 3 and filename[1] == ":" and filename[2] in ("\\", "/"):
            return filename

        base_dir = Path("D:/Chloe") if Path("D:/Chloe").exists() else Path.home() / "Desktop"

        if location:
            loc_lower = location.lower().strip()
            if loc_lower in self.dir_map:
                base_dir = Path(self.dir_map[loc_lower])
            elif loc_lower in ["desktop", "the desktop"]:
                base_dir = Path.home() / "Desktop"
            elif loc_lower in ["downloads", "the downloads"]:
                base_dir = Path.home() / "Downloads"
            elif loc_lower in ["d drive", "d:", "d", "local disk d"]:
                base_dir = Path("D:/")
            elif loc_lower in ["c drive", "c:", "c", "local disk c"]:
                base_dir = Path("C:/")

        return str(base_dir / filename)

    def _extract_drive_or_path_intent(self, text: str) -> Optional[NLPEntityResult]:
        """Extract explicit drive letters or folder paths to open in Windows Explorer."""
        explicit_drive_match = re.search(r'(?:open|launch|explore|go\s+to|show\s+me)?\s*(?:the\s+)?([a-zA-Z]:(?:[\\/][^\s*?"<>|]*)?)', text)
        if explicit_drive_match:
            path_found = explicit_drive_match.group(1).strip()
            if len(path_found) == 2 and path_found[1] == ':':
                path_found = f"{path_found.upper()}\\"
            return NLPEntityResult(
                intent="OPEN_PATH",
                confidence=0.98,
                entities={"target_path": path_found, "type": "drive_or_folder"},
                tool_name="launch_app",
                tool_params={"app_name": path_found},
                instant_response=f"Opening {path_found} in File Explorer.",
                normalized_text=text
            )

        open_prefix = re.match(r'^(?:open|launch|explore|go\s+to|show\s+me)\s+(?:the\s+)?(?:folder\s+)?(.+)$', text)
        if open_prefix:
            target = open_prefix.group(1).strip()
            target_cleaned = re.sub(r'\s+(?:folder|directory|drive)$', '', target).strip()
            
            if target_cleaned in self.dir_map:
                resolved_path = self.dir_map[target_cleaned]
                return NLPEntityResult(
                    intent="OPEN_PATH",
                    confidence=0.95,
                    entities={"target_path": resolved_path, "alias": target_cleaned},
                    tool_name="launch_app",
                    tool_params={"app_name": resolved_path},
                    instant_response=f"Opening {target_cleaned.title()} ({resolved_path}).",
                    normalized_text=text
                )

        return None

    def _extract_system_control_intent(self, text: str) -> Optional[NLPEntityResult]:
        """Detect PC Lock, Sleep, and Volume control intents."""
        if any(phrase in text for phrase in ["lock pc", "lock workstation", "lock computer", "lock screen", "lock windows"]):
            return NLPEntityResult(
                intent="SYSTEM_LOCK",
                confidence=0.99,
                entities={"action": "lock"},
                tool_name="system_control",
                tool_params={"action": "lock"},
                instant_response="Locking your workstation now.",
                normalized_text=text
            )
        return None

    def _extract_app_launch_intent(self, text: str) -> Optional[NLPEntityResult]:
        """Detect and slot fill desktop applications from natural speech."""
        patterns = [
            r'^(?:open|launch|start|run)\s+(?:the\s+)?(?:app\s+)?(.+)$',
            r'^can\s+you\s+(?:open|launch|start)\s+(?:the\s+)?(.+)$',
            r'^please\s+(?:open|launch|start)\s+(?:the\s+)?(.+)$'
        ]

        target_app = None
        for pattern in patterns:
            match = re.match(pattern, text)
            if match:
                target_app = match.group(1).strip()
                break

        if not target_app:
            return None

        cleaned_app = re.sub(r'\s+(?:app|application|program)$', '', target_app).strip()
        
        if cleaned_app in self.app_map:
            resolved_exec = self.app_map[cleaned_app]
            return NLPEntityResult(
                intent="LAUNCH_APP",
                confidence=0.96,
                entities={"app_name": cleaned_app, "executable": resolved_exec},
                tool_name="launch_app",
                tool_params={"app_name": resolved_exec},
                instant_response=f"Launching {cleaned_app.title()}.",
                normalized_text=text
            )

        for key, exe in self.app_map.items():
            if key in cleaned_app or cleaned_app in key:
                return NLPEntityResult(
                    intent="LAUNCH_APP",
                    confidence=0.88,
                    entities={"app_name": key, "executable": exe, "original_query": cleaned_app},
                    tool_name="launch_app",
                    tool_params={"app_name": exe},
                    instant_response=f"Launching {key.title()}.",
                    normalized_text=text
                )

        if len(cleaned_app.split()) <= 3 and not any(w in cleaned_app for w in ["what", "why", "how", "who", "when", "tell", "explain"]):
            return NLPEntityResult(
                intent="LAUNCH_APP",
                confidence=0.75,
                entities={"app_name": cleaned_app, "executable": cleaned_app},
                tool_name="launch_app",
                tool_params={"app_name": cleaned_app},
                instant_response=f"Opening {cleaned_app.title()}.",
                normalized_text=text
            )

        return None

    def _extract_math_intent(self, text: str) -> Optional[NLPEntityResult]:
        """Perform sub-millisecond safe arithmetic calculations without LLM hallucinations."""
        pct_match = re.search(r'(?:what\s+is\s+)?(\d+(?:\.\d+)?)\s*(?:%|percent)\s+of\s+(\d+(?:\.\d+)?)', text)
        if pct_match:
            pct_val = float(pct_match.group(1))
            base_val = float(pct_match.group(2))
            res = (pct_val / 100.0) * base_val
            formatted_res = f"{res:.2f}".rstrip('0').rstrip('.')
            return NLPEntityResult(
                intent="QUICK_CALC",
                confidence=0.99,
                entities={"percent": pct_val, "base": base_val, "result": res},
                instant_response=f"{pct_val}% of {base_val} is {formatted_res}.",
                normalized_text=text
            )

        calc_prefix = re.match(r'^(?:calculate|compute|what\s+is|solve)\s+([0-9\s\+\-\*\/\(\)\.\^]+)$', text)
        if calc_prefix:
            expr = calc_prefix.group(1).strip()
            if re.match(r'^[0-9\s\+\-\*\/\(\)\.\^]+$', expr) and any(op in expr for op in ['+', '-', '*', '/', '^']):
                try:
                    sanitized_expr = expr.replace('^', '**')
                    if not re.search(r'[a-zA-Z_]', sanitized_expr):
                        val = eval(sanitized_expr, {"__builtins__": None}, {})
                        formatted_val = f"{val:.4f}".rstrip('0').rstrip('.') if isinstance(val, float) else str(val)
                        return NLPEntityResult(
                            intent="QUICK_CALC",
                            confidence=0.98,
                            entities={"expression": expr, "result": val},
                            instant_response=f"{expr} = {formatted_val}",
                            normalized_text=text
                        )
                except Exception as e:
                    logger.debug(f"Math evaluation skipped: {e}")

        return None

    def _extract_web_search_intent(self, text: str) -> Optional[NLPEntityResult]:
        """Extract explicit web search requests."""
        search_match = re.match(r'^(?:search\s+(?:google\s+)?(?:for\s+)?|google\s+)(.+)$', text)
        if search_match:
            query = search_match.group(1).strip()
            if query and not any(w in query for w in ["file", "directory", "disk", "folder"]):
                return NLPEntityResult(
                    intent="WEB_SEARCH",
                    confidence=0.85,
                    entities={"query": query},
                    tool_name="web_search",
                    tool_params={"query": query},
                    instant_response=f"Searching the web for '{query}'...",
                    normalized_text=text
                )
        return None


# Global Singleton NLP Engine Instance
nlp_engine = NLPEngine()
