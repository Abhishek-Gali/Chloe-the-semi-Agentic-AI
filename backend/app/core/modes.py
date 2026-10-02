"""
Project Chloe - Operating Modes & Security Policies
Defines the 3 core modes:
1. FULLY_ISOLATED: Air-Gapped Local (Ollama Qwen, 0 internet traffic, read-only system)
2. PARTIALLY_ISOLATED: Fast Hybrid Local (Groq Llama 3 / Qwen, full tools, sub-second latency)
3. COMPLETELY_OPEN: Frontier Cloud (Gemini Flash, full tools, deep multi-step reasoning)
"""

from enum import Enum
from typing import Dict, Any

class OperatingMode(str, Enum):
    FULLY_ISOLATED = "FULLY_ISOLATED"
    PARTIALLY_ISOLATED = "PARTIALLY_ISOLATED"
    COMPLETELY_OPEN = "COMPLETELY_OPEN"

class ModePolicy:
    POLICIES: Dict[OperatingMode, Dict[str, Any]] = {
        OperatingMode.FULLY_ISOLATED: {
            "name": "Air-Gapped Local",
            "description": "Local Ollama LLM, 100% offline, execution of whitelisted local commands/utilities allowed, file writing prohibited.",
            "allow_internet": False,
            "allow_write_ops": False,
            "allow_shell_commands": True,
            "preferred_engine": "ollama",
            "badge_color": "#10b981", # Emerald
            "icon": "shield-lock"
        },
        OperatingMode.PARTIALLY_ISOLATED: {
            "name": "Fast Hybrid Local",
            "description": "Sub-second Groq streaming inference with full tool permissions for apps, files, shell, and web research.",
            "allow_internet": True,
            "allow_write_ops": True,
            "allow_shell_commands": True,
            "preferred_engine": "groq",
            "badge_color": "#3b82f6", # Blue
            "icon": "zap"
        },
        OperatingMode.COMPLETELY_OPEN: {
            "name": "Frontier Cloud",
            "description": "Gemini reasoning, full internet access, read/write ops enabled, shell command execution disabled.",
            "allow_internet": True,
            "allow_write_ops": True,
            "allow_shell_commands": False,
            "preferred_engine": "gemini",
            "badge_color": "#8b5cf6", # Purple
            "icon": "cpu"
        }
    }

    @classmethod
    def get_policy(cls, mode: OperatingMode) -> Dict[str, Any]:
        return cls.POLICIES.get(mode, cls.POLICIES[OperatingMode.PARTIALLY_ISOLATED])

    @classmethod
    def is_action_allowed(cls, mode: OperatingMode, action_type: str) -> bool:
        policy = cls.get_policy(mode)
        
        # 1. launch_app, query_vault, and explore_directory are ALWAYS allowed in all modes
        if action_type in ["launch_app", "query_vault", "explore_directory"]:
            return True
            
        # 2. File read/write operations (e.g. write_file, create_folder, etc.)
        if action_type in ["write_file", "create_folder", "open_notepad_with_content"]:
            return policy["allow_write_ops"]
            
        # 3. Running shell/cmd commands
        if action_type in ["run_shell_command", "get_tailscale_status"]:
            return policy["allow_shell_commands"]
            
        # 4. Web searches
        if action_type == "web_search":
            return policy["allow_internet"]
            
        return True
