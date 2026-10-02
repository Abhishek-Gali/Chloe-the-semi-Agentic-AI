"""
Project Chloe - System Automation MCP Tools
Handles OS operations: App launching, Notepad popup, file management, sandboxed shell execution, and hardware diagnostics.
"""

import os
import sys
import psutil
import subprocess
import webbrowser
import tempfile
import logging
import re
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Strict shell execution whitelist
ALLOWED_SHELL_COMMANDS = {
    "ping", "ipconfig", "ifconfig", "traceroute", "tracert", "netstat",
    "git", "python", "node", "npm", "dir", "ls", "echo", "systeminfo", "whoami", "hostname"
}

# App launcher lookup table for Windows with extensive aliases
APP_REGISTRY = {
    "chrome": ["start", "chrome"],
    "google chrome": ["start", "chrome"],
    "browser": ["start", "chrome"],
    "vscode": ["code"],
    "vs code": ["code"],
    "code": ["code"],
    "visual studio code": ["code"],
    "notepad": ["notepad.exe"],
    "notepad.exe": ["notepad.exe"],
    "text editor": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calc.exe": ["calc.exe"],
    "calculator": ["calc.exe"],
    "spotify": ["start", "spotify:"],
    "discord": ["start", "discord:"],
    "terminal": ["start", "wt.exe"],
    "windows terminal": ["start", "wt.exe"],
    "wt": ["start", "wt.exe"],
    "cmd": ["start", "cmd.exe"],
    "cmd.exe": ["start", "cmd.exe"],
    "command prompt": ["start", "cmd.exe"],
    "command": ["start", "cmd.exe"],
    "powershell": ["start", "powershell.exe"],
    "powershell.exe": ["start", "powershell.exe"],
    "pwsh": ["start", "pwsh.exe"],
    "explorer": ["explorer.exe"],
    "file explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "task manager": ["start", "taskmgr.exe"],
    "taskmgr": ["start", "taskmgr.exe"],
    "settings": ["start", "ms-settings:"],
    "whatsapp": ["start", "whatsapp:"]
}

class SystemTools:
    _cached_shortcuts = None

    @classmethod
    def _get_installed_shortcuts(cls) -> Dict[str, str]:
        if cls._cached_shortcuts is not None:
            return cls._cached_shortcuts

        shortcuts = {}
        paths = [
            os.path.join(os.environ.get('ProgramData', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs'),
            os.path.join(os.environ.get('APPDATA', ''), 'Microsoft', 'Windows', 'Start Menu', 'Programs')
        ]

        for p in paths:
            if os.path.exists(p):
                for root, dirs, files in os.walk(p):
                    for file in files:
                        if file.endswith('.lnk'):
                            name = os.path.splitext(file)[0].lower().strip()
                            shortcuts[name] = os.path.join(root, file)
                            
                            # Register first word alias (e.g. "Google Chrome" -> "chrome")
                            if " " in name:
                                first_word = name.split()[0]
                                if len(first_word) > 2 and first_word not in ["microsoft", "install", "intel", "uninstall", "adobe", "google"]:
                                    if first_word not in shortcuts:
                                        shortcuts[first_word] = os.path.join(root, file)

        cls._cached_shortcuts = shortcuts
        logger.info(f"SystemTools: Cached {len(shortcuts)} installed applications from Start Menu.")
        return shortcuts

    @staticmethod
    def launch_app(app_name: str) -> Dict[str, Any]:
        """Launches a desktop application, file, directory, or website URL in the foreground with zero console popups."""
        raw_name = app_name.strip().strip('"').strip("'")
        norm_name = raw_name.lower().rstrip(".!?,")

        # 1. Direct Existing File Path or Directory on Disk (e.g. "E:\Chloe Portfolio\index.html", "D:\WebScraper")
        if os.path.exists(raw_name) or os.path.exists(app_name):
            target = raw_name if os.path.exists(raw_name) else app_name
            try:
                if sys.platform == "win32":
                    os.startfile(target)
                else:
                    subprocess.Popen(["xdg-open", target])
                logger.info(f"SystemTools: Opened target on disk: {target}")
                return {"status": "success", "message": f"Opened {os.path.basename(target) or target} successfully."}
            except Exception as e:
                logger.error(f"Failed to open path {target}: {e}")
                return {"status": "error", "message": str(e)}

        # 2. URL / Domain launcher (e.g. "github.com", "youtube.com", "https://...", "google.com")
        url_keywords = ["github", "youtube", "google", "gmail", "reddit", "twitter", "x.com", "linkedin", "chatgpt"]
        if (norm_name.startswith("http://") or norm_name.startswith("https://") or 
            any(norm_name.endswith(ext) for ext in [".com", ".org", ".net", ".io", ".dev", ".ai", ".html"]) or
            any(k == norm_name for k in url_keywords)):
            url = raw_name
            if not url.startswith("http://") and not url.startswith("https://"):
                if "." not in url:
                    url = f"https://www.{url}.com"
                else:
                    url = f"https://{url}"
            try:
                import webbrowser
                webbrowser.open(url)
                logger.info(f"SystemTools: Opened website in browser: {url}")
                return {"status": "success", "message": f"Opened {url} in your browser.", "url": url}
            except Exception as e:
                logger.error(f"Failed to open browser URL {url}: {e}")
                return {"status": "error", "message": str(e)}

        # 3. Windows Desktop Application & Drive Launcher
        if sys.platform == "win32":
            try:
                # Drive Letter Launcher (e.g. "e drive", "d drive", "c drive", "e:", "e")
                drive_match = re.match(r'^([a-zA-Z])(?:\s+drive|:|)$', norm_name)
                if drive_match:
                    drive_letter = drive_match.group(1).upper()
                    os.startfile(f"{drive_letter}:\\")
                    return {"status": "success", "message": f"Successfully opened {drive_letter} drive in Explorer."}

                # Try matching dynamic installed applications shortcuts map
                shortcuts_map = SystemTools._get_installed_shortcuts()
                if norm_name in shortcuts_map:
                    lnk_path = shortcuts_map[norm_name]
                    try:
                        os.startfile(lnk_path)
                        return {"status": "success", "message": f"Successfully launched {app_name}."}
                    except Exception as e:
                        logger.error(f"Failed to open shortcut {lnk_path}: {e}")

                if norm_name in ["notepad", "notepad.exe", "text editor"]:
                    subprocess.Popen('start notepad', shell=True)
                    return {"status": "success", "message": "Successfully launched Notepad."}

                elif norm_name in ["whatsapp"]:
                    subprocess.Popen('start whatsapp:', shell=True)
                    return {"status": "success", "message": "Successfully launched WhatsApp."}

                elif norm_name in ["chrome", "google chrome", "browser"]:
                    subprocess.Popen('start chrome', shell=True)
                    return {"status": "success", "message": "Successfully launched Google Chrome."}

                elif norm_name in ["vscode", "vs code", "code", "visual studio code"]:
                    code_exe = os.path.expandvars(r'%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe')
                    if os.path.exists(code_exe):
                        os.startfile(code_exe)
                    else:
                        subprocess.Popen('start code', shell=True)
                    return {"status": "success", "message": "Successfully launched VS Code."}

                elif norm_name in ["cmd", "cmd.exe", "command prompt", "command"]:
                    subprocess.Popen('start cmd', shell=True)
                    return {"status": "success", "message": "Successfully launched Command Prompt."}

                elif norm_name in ["calc", "calculator", "calc.exe"]:
                    subprocess.Popen('start calc', shell=True)
                    return {"status": "success", "message": "Successfully launched Calculator."}

                elif norm_name in ["taskmgr", "task manager"]:
                    subprocess.Popen('start taskmgr', shell=True)
                    return {"status": "success", "message": "Successfully launched Task Manager."}

                elif norm_name in ["terminal", "windows terminal", "wt"]:
                    subprocess.Popen('start wt', shell=True)
                    return {"status": "success", "message": "Successfully launched Windows Terminal."}

                elif norm_name in ["powershell", "powershell.exe", "pwsh"]:
                    subprocess.Popen('start powershell', shell=True)
                    return {"status": "success", "message": "Successfully launched PowerShell."}

                elif norm_name in ["settings"]:
                    subprocess.Popen('start ms-settings:', shell=True)
                    return {"status": "success", "message": "Successfully launched Windows Settings."}

                elif norm_name in ["explorer", "file explorer", "files"]:
                    subprocess.Popen('start explorer', shell=True)
                    return {"status": "success", "message": "Successfully launched File Explorer."}

                else:
                    try:
                        os.startfile(raw_name)
                        return {"status": "success", "message": f"Successfully launched {app_name}."}
                    except Exception:
                        subprocess.Popen(f'start "" "{raw_name}"', shell=True, creationflags=0x08000000)
                        return {"status": "success", "message": f"Successfully launched {app_name}."}
            except Exception as e:
                logger.error(f"Error launching {app_name}: {e}")
                return {"status": "error", "message": f"Failed to launch {app_name}: {str(e)}"}
        else:
            try:
                cmd = APP_REGISTRY.get(norm_name, [norm_name])
                subprocess.Popen(cmd)
                return {"status": "success", "message": f"Successfully launched {app_name}."}
            except Exception as e:
                return {"status": "error", "message": str(e)}

    @staticmethod
    def open_notepad_with_content(content: str, title: str = "Chloe_Note") -> Dict[str, Any]:
        """Opens Windows Notepad with pre-populated content in foreground."""
        try:
            tmp_dir = tempfile.gettempdir()
            clean_title = "".join(c for c in title if c.isalnum() or c in ('_', '-'))
            if not clean_title:
                clean_title = "Chloe_Note"
            file_path = os.path.join(tmp_dir, f"{clean_title}.txt")
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
                
            if sys.platform == "win32":
                try:
                    os.startfile(file_path)
                except Exception:
                    subprocess.Popen(f'start "" notepad "{file_path}"', shell=True)
            else:
                subprocess.Popen(["gedit", file_path])
                
            return {"status": "success", "message": f"Opened Notepad with {len(content)} characters of text."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to open Notepad: {str(e)}"}

    @staticmethod
    def open_chrome_search(query: str) -> Dict[str, Any]:
        """Opens Google Chrome or default browser with a search query."""
        try:
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            return {"status": "success", "message": f"Opened browser search for '{query}'."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to open browser: {str(e)}"}

    @staticmethod
    def write_file(path: str, content: str) -> Dict[str, Any]:
        """Safely writes text to a file path."""
        try:
            target_path = Path(path).resolve()
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "message": f"File written successfully to {target_path}."}
        except Exception as e:
            return {"status": "error", "message": f"Write failed: {str(e)}"}

    @staticmethod
    def create_folder(path: str) -> Dict[str, Any]:
        """Creates a directory folder structure."""
        try:
            target_dir = Path(path).resolve()
            target_dir.mkdir(parents=True, exist_ok=True)
            return {"status": "success", "message": f"Directory created at {target_dir}."}
        except Exception as e:
            return {"status": "error", "message": f"Directory creation failed: {str(e)}"}

    @staticmethod
    def explore_directory(path: str = ".") -> Dict[str, Any]:
        """Lists files and folders with sizes."""
        try:
            dir_path = Path(path).resolve()
            if not dir_path.exists():
                return {"status": "error", "message": f"Path '{path}' does not exist."}

            entries = []
            for item in dir_path.iterdir():
                try:
                    is_dir = item.is_dir()
                    size = item.stat().st_size if not is_dir else 0
                    entries.append({
                        "name": item.name,
                        "type": "directory" if is_dir else "file",
                        "size_bytes": size
                    })
                except Exception:
                    continue
            return {"status": "success", "path": str(dir_path), "entries": entries[:100]}
        except Exception as e:
            return {"status": "error", "message": f"Explore failed: {str(e)}"}

    @staticmethod
    def run_shell_command(command: str) -> Dict[str, Any]:
        """Executes a sandboxed shell command with safety checks."""
        try:
            trimmed = command.strip()
            first_word = trimmed.split()[0].lower() if trimmed else ""

            # Check if command is in whitelist
            if first_word not in ALLOWED_SHELL_COMMANDS and not any(trimmed.startswith(w) for w in ALLOWED_SHELL_COMMANDS):
                return {
                    "status": "blocked",
                    "message": f"Command '{first_word}' is restricted for security. Allowed: {list(ALLOWED_SHELL_COMMANDS)}"
                }

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=15
            )

            return {
                "status": "success",
                "return_code": result.returncode,
                "stdout": result.stdout[:2000] if result.stdout else "",
                "stderr": result.stderr[:1000] if result.stderr else ""
            }
        except subprocess.TimeoutExpired:
            return {"status": "timeout", "message": "Command execution timed out after 15 seconds."}
        except Exception as e:
            return {"status": "error", "message": f"Execution error: {str(e)}"}

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Gathers real-time OS and hardware metrics."""
        try:
            cpu_pct = psutil.cpu_percent(interval=0.1)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage('C:' if sys.platform == 'win32' else '/')
            battery = psutil.sensors_battery()

            battery_info = None
            if battery:
                battery_info = {
                    "percent": battery.percent,
                    "power_plugged": battery.power_plugged,
                    "time_left_mins": round(battery.secsleft / 60) if battery.secsleft > 0 else None
                }

            return {
                "status": "success",
                "cpu": {
                    "percent": cpu_pct,
                    "cores_logical": psutil.cpu_count(logical=True),
                    "cores_physical": psutil.cpu_count(logical=False)
                },
                "memory": {
                    "total_gb": round(mem.total / (1024**3), 2),
                    "available_gb": round(mem.available / (1024**3), 2),
                    "used_percent": mem.percent
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_percent": disk.percent
                },
                "battery": battery_info,
                "platform": sys.platform,
                "tailscale": SystemTools.get_tailscale_status()
            }
        except Exception as e:
            return {"status": "error", "message": f"Failed to retrieve telemetry: {str(e)}"}

    @staticmethod
    def get_tailscale_status() -> Dict[str, Any]:
        """Detects Tailscale interface IP and daemon status."""
        tailscale_ip = None
        # 1. Try checking network interfaces for 100.x.y.z CGNAT address
        try:
            for iface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET and addr.address.startswith("100."):
                        tailscale_ip = addr.address
                        break
                if tailscale_ip:
                    break
        except Exception:
            pass

        # 2. Try running tailscale CLI if available
        if not tailscale_ip:
            try:
                res = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=2)
                if res.returncode == 0 and res.stdout.strip():
                    tailscale_ip = res.stdout.strip()
            except Exception:
                pass

        return {
            "installed": tailscale_ip is not None,
            "ip": tailscale_ip or "Not Connected",
            "remote_gateway_url": f"http://{tailscale_ip}:8000" if tailscale_ip else None,
            "remote_ws_url": f"ws://{tailscale_ip}:8000/ws/audio" if tailscale_ip else None
        }
