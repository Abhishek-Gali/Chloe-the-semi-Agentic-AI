"""
Project Chloe 2.0 - Interactive Windows Setup & Installation Wizard
Provides a modern, dark-themed installer wizard for deploying Project Chloe on any Windows machine.
Includes automated setup for Ollama Local LLMs and Air-Gapped offline models.
"""

import os
import sys
import time
import shutil
import tempfile
import subprocess
import threading
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

INSTALLER_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = INSTALLER_DIR.parent

# Theme Colors
BG_DARK = "#080d14"
CARD_BG = "#0f172a"
BORDER_COLOR = "#1e293b"
ACCENT_CYAN = "#00f0ff"
ACCENT_PURPLE = "#a855f7"
TEXT_MAIN = "#f8fafc"
TEXT_MUTED = "#94a3b8"
BTN_BG = "#0284c7"
BTN_HOVER = "#0369a1"

class ChloeSetupWizard(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Project Chloe 2.0 // Windows Setup Wizard")
        self.geometry("740x580")
        self.resizable(False, False)
        self.configure(bg=BG_DARK)

        # Default Installation State
        user_home = Path(os.environ.get("USERPROFILE", str(Path.home())))
        default_install = user_home / "AppData" / "Local" / "Project Chloe"

        self.install_dir = tk.StringVar(value=str(default_install))
        self.operating_mode = tk.StringVar(value="PARTIALLY_ISOLATED")
        self.groq_key = tk.StringVar(value="")
        self.gemini_key = tk.StringVar(value="")
        self.default_voice = tk.StringVar(value="Bella (US Female - Natural)")

        # Ollama & Local Model Options
        self.install_ollama = tk.BooleanVar(value=True)
        self.local_model = tk.StringVar(value="qwen2.5:1.5b")

        # Integration & Shortcuts
        self.create_desktop_shortcut = tk.BooleanVar(value=True)
        self.create_start_menu_shortcut = tk.BooleanVar(value=True)
        self.launch_on_startup = tk.BooleanVar(value=False)
        self.launch_after_install = tk.BooleanVar(value=True)

        self.current_step = 0
        self.pages = []

        self._init_styles()
        self._build_ui_scaffolding()
        self._create_pages()
        self._show_page(0)

    def _init_styles(self):
        """Configures ttk widget styles."""
        self.style = ttk.Style(self)
        self.style.theme_use("clam")
        
        self.style.configure("TProgressbar",
            thickness=14,
            troughcolor=CARD_BG,
            background=ACCENT_CYAN,
            bordercolor=BORDER_COLOR
        )
        self.style.configure("TCombobox",
            fieldbackground=BG_DARK,
            background=CARD_BG,
            foreground=TEXT_MAIN,
            bordercolor=BORDER_COLOR,
            darkcolor=BG_DARK,
            lightcolor=BORDER_COLOR
        )

    def _build_ui_scaffolding(self):
        """Builds top header banner, center page container, and bottom navigation bar."""
        # Top Header Banner
        self.header_frame = tk.Frame(self, bg=CARD_BG, height=70, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)
        self.header_frame.pack_propagate(False)

        title_lbl = tk.Label(self.header_frame, text="PROJECT CHLOE 2.0", font=("Segoe UI", 16, "bold"), fg=ACCENT_CYAN, bg=CARD_BG)
        title_lbl.pack(side=tk.LEFT, padx=25, pady=12)

        version_badge = tk.Label(self.header_frame, text="SETUP WIZARD", font=("Segoe UI", 9, "bold"), fg=ACCENT_PURPLE, bg=BORDER_COLOR, padx=8, pady=3)
        version_badge.pack(side=tk.LEFT, pady=18)

        # Center Container
        self.container = tk.Frame(self, bg=BG_DARK)
        self.container.pack(fill=tk.BOTH, expand=True, padx=25, pady=15)

        # Bottom Navigation Bar
        self.nav_frame = tk.Frame(self, bg=CARD_BG, height=60, bd=0, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.nav_frame.pack(fill=tk.X, side=tk.BOTTOM)
        self.nav_frame.pack_propagate(False)

        self.btn_cancel = tk.Button(self.nav_frame, text="Cancel", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=CARD_BG, activebackground=BORDER_COLOR, activeforeground=TEXT_MAIN, bd=1, relief=tk.FLAT, padx=15, pady=6, command=self.destroy)
        self.btn_cancel.pack(side=tk.LEFT, padx=20, pady=12)

        self.btn_next = tk.Button(self.nav_frame, text="Next >", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg=BTN_BG, activebackground=BTN_HOVER, activeforeground="#ffffff", bd=0, padx=20, pady=6, command=self._next_page)
        self.btn_next.pack(side=tk.RIGHT, padx=20, pady=12)

        self.btn_back = tk.Button(self.nav_frame, text="< Back", font=("Segoe UI", 10), fg=TEXT_MAIN, bg=CARD_BG, activebackground=BORDER_COLOR, activeforeground=TEXT_MAIN, bd=1, relief=tk.FLAT, padx=15, pady=6, command=self._back_page)
        self.btn_back.pack(side=tk.RIGHT, pady=12)

    def _create_pages(self):
        """Creates the individual installer step frames."""
        # --- PAGE 0: Welcome ---
        p0 = tk.Frame(self.container, bg=BG_DARK)
        lbl_welcome = tk.Label(p0, text="Welcome to Project Chloe 2.0", font=("Segoe UI", 18, "bold"), fg=TEXT_MAIN, bg=BG_DARK)
        lbl_welcome.pack(anchor="w", pady=(10, 5))

        lbl_desc = tk.Label(p0, text="This wizard will deploy Abhishek's elite personal AI assistant on your system.\nConfiguring continuous learning memory, Kokoro-82M neural TTS, and optional Ollama local models.", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_DARK, justify="left")
        lbl_desc.pack(anchor="w", pady=(0, 15))

        feat_box = tk.Frame(p0, bg=CARD_BG, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=15)
        feat_box.pack(fill=tk.BOTH, expand=True)

        features = [
            ("⚡ Sub-Millisecond NLP Engine", "Executes system directives & app launches in under 0.5ms."),
            ("🧠 3-Tier Continuous Learning", "Learns habits, caches tool workflows, & trains local models."),
            ("🔊 Neural Voice Synthesis", "Kokoro-82M ONNX runs 100% offline with zero GPU dependencies."),
            ("🛡️ Local Air-Gapped Intelligence", "Ollama LLM integration with automatic silent installer & model configuration.")
        ]
        for title, subtitle in features:
            f_frame = tk.Frame(feat_box, bg=CARD_BG)
            f_frame.pack(fill=tk.X, pady=5)
            tk.Label(f_frame, text=title, font=("Segoe UI", 10, "bold"), fg=ACCENT_CYAN, bg=CARD_BG).pack(anchor="w")
            tk.Label(f_frame, text=subtitle, font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w")

        self.pages.append(p0)

        # --- PAGE 1: Installation Directory ---
        p1 = tk.Frame(self.container, bg=BG_DARK)
        tk.Label(p1, text="Select Destination Location", font=("Segoe UI", 16, "bold"), fg=TEXT_MAIN, bg=BG_DARK).pack(anchor="w", pady=(10, 5))
        tk.Label(p1, text="Choose the directory where Project Chloe will be deployed.", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_DARK).pack(anchor="w", pady=(0, 20))

        dir_box = tk.Frame(p1, bg=CARD_BG, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
        dir_box.pack(fill=tk.X)

        tk.Label(dir_box, text="Destination Folder:", font=("Segoe UI", 10, "bold"), fg=TEXT_MAIN, bg=CARD_BG).pack(anchor="w", pady=(0, 8))
        
        entry_frame = tk.Frame(dir_box, bg=CARD_BG)
        entry_frame.pack(fill=tk.X)
        
        entry_dir = tk.Entry(entry_frame, textvariable=self.install_dir, font=("Segoe UI", 10), bg=BG_DARK, fg=TEXT_MAIN, insertbackground=ACCENT_CYAN, bd=1, relief=tk.FLAT)
        entry_dir.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5, padx=(0, 10))

        btn_browse = tk.Button(entry_frame, text="Browse...", font=("Segoe UI", 9, "bold"), fg=TEXT_MAIN, bg=BORDER_COLOR, activebackground=BTN_BG, activeforeground="#fff", bd=0, padx=12, pady=4, command=self._browse_dir)
        btn_browse.pack(side=tk.RIGHT)

        tk.Label(p1, text="Space required: ~350 MB (Base) / ~1.8 GB (with Local Ollama) | Space available: >10 GB", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_DARK).pack(anchor="w", pady=15)
        self.pages.append(p1)

        # --- PAGE 2: AI Engine, Ollama & API Keys ---
        p2 = tk.Frame(self.container, bg=BG_DARK)
        tk.Label(p2, text="AI Engine & Model Configuration", font=("Segoe UI", 16, "bold"), fg=TEXT_MAIN, bg=BG_DARK).pack(anchor="w", pady=(5, 3))
        tk.Label(p2, text="Configure operating mode, local offline models (Ollama), and optional cloud keys.", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=BG_DARK).pack(anchor="w", pady=(0, 10))

        cfg_box = tk.Frame(p2, bg=CARD_BG, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=15, pady=12)
        cfg_box.pack(fill=tk.BOTH, expand=True)

        # Mode Selection
        mode_row = tk.Frame(cfg_box, bg=CARD_BG)
        mode_row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(mode_row, text="Default Operating Mode:", font=("Segoe UI", 9, "bold"), fg=TEXT_MAIN, bg=CARD_BG).pack(side=tk.LEFT)
        mode_cb = ttk.Combobox(mode_row, textvariable=self.operating_mode, values=["PARTIALLY_ISOLATED", "FULLY_ISOLATED", "COMPLETELY_OPEN"], state="readonly", font=("Segoe UI", 9), width=24)
        mode_cb.pack(side=tk.RIGHT)
        mode_cb.bind("<<ComboboxSelected>>", self._on_mode_change)

        # Ollama Local AI Section (Highlight Box)
        ollama_frame = tk.Frame(cfg_box, bg=BG_DARK, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=12, pady=10)
        ollama_frame.pack(fill=tk.X, pady=6)

        cb_ollama = tk.Checkbutton(
            ollama_frame,
            text="Download & Configure Ollama Local AI (Air-Gapped Offline Support, ~1.5 GB)",
            variable=self.install_ollama,
            font=("Segoe UI", 9, "bold"),
            fg=ACCENT_CYAN,
            bg=BG_DARK,
            selectcolor=CARD_BG,
            activebackground=BG_DARK,
            activeforeground=ACCENT_CYAN,
            command=self._toggle_ollama_options
        )
        cb_ollama.pack(anchor="w")

        tk.Label(
            ollama_frame,
            text="If checked, wizard automatically downloads Ollama for Windows (if missing),\npulls local model, builds the chloe:latest persona, and configures zero-latency offline mode.",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
            justify="left"
        ).pack(anchor="w", padx=(20, 0), pady=(2, 6))

        self.model_row = tk.Frame(ollama_frame, bg=BG_DARK)
        self.model_row.pack(fill=tk.X, padx=(20, 0), pady=(0, 2))
        tk.Label(self.model_row, text="Local Base Model to Pull:", font=("Segoe UI", 8, "bold"), fg=TEXT_MAIN, bg=BG_DARK).pack(side=tk.LEFT)
        self.model_cb = ttk.Combobox(
            self.model_row,
            textvariable=self.local_model,
            values=["qwen2.5:1.5b", "qwen2.5:0.5b", "qwen2.5:3b", "qwen2.5-coder:1.5b"],
            state="readonly",
            font=("Segoe UI", 8),
            width=20
        )
        self.model_cb.pack(side=tk.RIGHT)

        # Cloud Keys Section
        tk.Label(cfg_box, text="Cloud API Keys (Optional - for hybrid cloud inference):", font=("Segoe UI", 9, "bold"), fg=TEXT_MUTED, bg=CARD_BG).pack(anchor="w", pady=(8, 4))
        
        k1_row = tk.Frame(cfg_box, bg=CARD_BG)
        k1_row.pack(fill=tk.X, pady=2)
        tk.Label(k1_row, text="Groq API Key:", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=CARD_BG, width=16, anchor="w").pack(side=tk.LEFT)
        e_groq = tk.Entry(k1_row, textvariable=self.groq_key, font=("Segoe UI", 9), bg=BG_DARK, fg=TEXT_MAIN, insertbackground=ACCENT_CYAN, show="*", bd=1, relief=tk.FLAT)
        e_groq.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        k2_row = tk.Frame(cfg_box, bg=CARD_BG)
        k2_row.pack(fill=tk.X, pady=2)
        tk.Label(k2_row, text="Gemini API Key:", font=("Segoe UI", 8), fg=TEXT_MUTED, bg=CARD_BG, width=16, anchor="w").pack(side=tk.LEFT)
        e_gemini = tk.Entry(k2_row, textvariable=self.gemini_key, font=("Segoe UI", 9), bg=BG_DARK, fg=TEXT_MAIN, insertbackground=ACCENT_CYAN, show="*", bd=1, relief=tk.FLAT)
        e_gemini.pack(side=tk.RIGHT, fill=tk.X, expand=True)

        self.pages.append(p2)

        # --- PAGE 3: Shortcuts & Integration ---
        p3 = tk.Frame(self.container, bg=BG_DARK)
        tk.Label(p3, text="Select Additional Tasks", font=("Segoe UI", 16, "bold"), fg=TEXT_MAIN, bg=BG_DARK).pack(anchor="w", pady=(10, 5))
        tk.Label(p3, text="Select shortcuts and integration options for Windows.", font=("Segoe UI", 10), fg=TEXT_MUTED, bg=BG_DARK).pack(anchor="w", pady=(0, 20))

        opt_box = tk.Frame(p3, bg=CARD_BG, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
        opt_box.pack(fill=tk.BOTH, expand=True)

        cb1 = tk.Checkbutton(opt_box, text="Create a Desktop Shortcut", variable=self.create_desktop_shortcut, font=("Segoe UI", 10), fg=TEXT_MAIN, bg=CARD_BG, selectcolor=BG_DARK, activebackground=CARD_BG, activeforeground=ACCENT_CYAN)
        cb1.pack(anchor="w", pady=8)

        cb2 = tk.Checkbutton(opt_box, text="Create a Start Menu Program Entry", variable=self.create_start_menu_shortcut, font=("Segoe UI", 10), fg=TEXT_MAIN, bg=CARD_BG, selectcolor=BG_DARK, activebackground=CARD_BG, activeforeground=ACCENT_CYAN)
        cb2.pack(anchor="w", pady=8)

        cb3 = tk.Checkbutton(opt_box, text="Launch Chloe silently on Windows Startup", variable=self.launch_on_startup, font=("Segoe UI", 10), fg=TEXT_MAIN, bg=CARD_BG, selectcolor=BG_DARK, activebackground=CARD_BG, activeforeground=ACCENT_CYAN)
        cb3.pack(anchor="w", pady=8)

        self.pages.append(p3)

        # --- PAGE 4: Progress & Installation ---
        p4 = tk.Frame(self.container, bg=BG_DARK)
        tk.Label(p4, text="Installing Project Chloe 2.0...", font=("Segoe UI", 16, "bold"), fg=TEXT_MAIN, bg=BG_DARK).pack(anchor="w", pady=(10, 5))
        
        self.lbl_status = tk.Label(p4, text="Preparing installation files...", font=("Segoe UI", 10), fg=ACCENT_CYAN, bg=BG_DARK)
        self.lbl_status.pack(anchor="w", pady=(0, 10))

        self.progress_bar = ttk.Progressbar(p4, style="TProgressbar", mode="determinate")
        self.progress_bar.pack(fill=tk.X, pady=10)

        self.log_box = tk.Text(p4, height=13, bg=CARD_BG, fg=TEXT_MUTED, font=("Consolas", 9), bd=1, relief=tk.FLAT, highlightbackground=BORDER_COLOR, highlightthickness=1)
        self.log_box.pack(fill=tk.BOTH, expand=True, pady=5)

        self.pages.append(p4)

        # --- PAGE 5: Completion ---
        p5 = tk.Frame(self.container, bg=BG_DARK)
        tk.Label(p5, text="Installation Complete!", font=("Segoe UI", 18, "bold"), fg=ACCENT_CYAN, bg=BG_DARK).pack(anchor="w", pady=(10, 5))
        tk.Label(p5, text="Project Chloe 2.0 has been successfully installed on your computer.", font=("Segoe UI", 10), fg=TEXT_MAIN, bg=BG_DARK).pack(anchor="w", pady=(0, 20))

        success_box = tk.Frame(p5, bg=CARD_BG, bd=1, highlightbackground=BORDER_COLOR, highlightthickness=1, padx=20, pady=20)
        success_box.pack(fill=tk.BOTH, expand=True)

        tk.Label(success_box, text="Ready to Launch:", font=("Segoe UI", 11, "bold"), fg=TEXT_MAIN, bg=CARD_BG).pack(anchor="w", pady=(0, 8))
        tk.Label(success_box, text="• Web HUD: http://localhost:8000\n• Neural TTS: Kokoro-82M Active (Offline)\n• Continuous Learning Database: Initialized\n• Shortcuts Deployed to Desktop & Start Menu", font=("Segoe UI", 9), fg=TEXT_MUTED, bg=CARD_BG, justify="left").pack(anchor="w", pady=(0, 15))

        cb_launch = tk.Checkbutton(success_box, text="Launch Project Chloe immediately", variable=self.launch_after_install, font=("Segoe UI", 10, "bold"), fg=ACCENT_CYAN, bg=CARD_BG, selectcolor=BG_DARK, activebackground=CARD_BG, activeforeground=ACCENT_CYAN)
        cb_launch.pack(anchor="w")

        self.pages.append(p5)

    def _on_mode_change(self, event=None):
        """Auto-toggle Ollama if Fully Isolated is chosen."""
        if self.operating_mode.get() == "FULLY_ISOLATED":
            self.install_ollama.set(True)
            self._toggle_ollama_options()

    def _toggle_ollama_options(self):
        """Enables or disables model selection combobox."""
        state = "readonly" if self.install_ollama.get() else "disabled"
        self.model_cb.config(state=state)

    def _browse_dir(self):
        chosen = filedialog.askdirectory(initialdir=self.install_dir.get(), title="Select Project Chloe Installation Directory")
        if chosen:
            self.install_dir.set(str(Path(chosen)))

    def _show_page(self, index: int):
        self.current_step = index
        for i, p in enumerate(self.pages):
            if i == index:
                p.pack(fill=tk.BOTH, expand=True)
            else:
                p.pack_forget()

        # Update Navigation Buttons
        self.btn_back.config(state=tk.NORMAL if 0 < index < 4 else tk.DISABLED)
        
        if index == 3:
            self.btn_next.config(text="Install", bg=ACCENT_PURPLE)
        elif index == 4:
            self.btn_next.config(state=tk.DISABLED, text="Installing...")
            self.btn_cancel.config(state=tk.DISABLED)
            threading.Thread(target=self._run_installation, daemon=True).start()
        elif index == 5:
            self.btn_next.config(state=tk.NORMAL, text="Finish", bg=BTN_BG, command=self._finish_installer)
            self.btn_cancel.pack_forget()
        else:
            self.btn_next.config(state=tk.NORMAL, text="Next >", bg=BTN_BG, command=self._next_page)

    def _next_page(self):
        if self.current_step < len(self.pages) - 1:
            self._show_page(self.current_step + 1)

    def _back_page(self):
        if self.current_step > 0:
            self._show_page(self.current_step - 1)

    def _log(self, text: str):
        self.log_box.insert(tk.END, f"{text}\n")
        self.log_box.see(tk.END)

    def _find_ollama_binary(self) -> str | None:
        """Locates ollama CLI executable on system PATH or standard install dirs."""
        which_path = shutil.which("ollama")
        if which_path:
            return which_path
        
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
            Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
            Path(os.environ.get("ProgramFiles(x86)", "")) / "Ollama" / "ollama.exe"
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return None

    def _download_file(self, url: str, dest_path: Path, label: str = "installer"):
        """Downloads a remote file with streaming progress reports to the log UI."""
        self._log(f"[*] Downloading {label} from {url}...")
        req = urllib.request.Request(url, headers={"User-Agent": "ProjectChloeInstaller/2.0"})
        with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f_out:
            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_reported_mb = 0

            while True:
                chunk = resp.read(131072)  # 128KB chunks
                if not chunk:
                    break
                f_out.write(chunk)
                downloaded += len(chunk)
                mb_down = downloaded / (1024 * 1024)
                if mb_down - last_reported_mb >= 10:
                    last_reported_mb = mb_down
                    if total_size > 0:
                        pct = int(downloaded * 100 / total_size)
                        self._log(f"    -> Progress: {mb_down:.1f} MB / {total_size / (1024*1024):.1f} MB ({pct}%)")
                    else:
                        self._log(f"    -> Progress: {mb_down:.1f} MB downloaded...")

        self._log(f"[+] Download complete: {dest_path.name}")

    def _ensure_ollama_service(self, ollama_bin: str) -> bool:
        """Checks if Ollama daemon is responsive; starts it in background if needed."""
        url = "http://127.0.0.1:11434/api/tags"
        for _ in range(2):
            try:
                with urllib.request.urlopen(url, timeout=1.5) as r:
                    if r.status == 200:
                        return True
            except Exception:
                pass
            
            # Start service
            self._log("[*] Starting Ollama local background service...")
            creation_flags = 0x08000000 if os.name == 'nt' else 0  # CREATE_NO_WINDOW
            try:
                subprocess.Popen([ollama_bin, "serve"], creationflags=creation_flags)
            except Exception as e:
                self._log(f"[!] Warning launching ollama serve: {e}")

            # Wait up to 12 seconds for daemon to accept connections
            for wait_idx in range(12):
                time.sleep(1)
                try:
                    with urllib.request.urlopen(url, timeout=1.5) as r:
                        if r.status == 200:
                            self._log("[+] Ollama local service is up and responsive.")
                            return True
                except Exception:
                    pass

        return False

    def _setup_ollama_local(self, dest: Path):
        """Installs Ollama, pulls the chosen model, and creates the Chloe persona."""
        self._log("\n" + "=" * 50)
        self._log("[*] INITIATING OLLAMA LOCAL AI CONFIGURATION")
        self._log("=" * 50)

        ollama_bin = self._find_ollama_binary()
        if not ollama_bin:
            self._log("[*] Ollama not found on system. Preparing automatic installation...")
            temp_installer = Path(tempfile.gettempdir()) / "OllamaSetup.exe"
            try:
                self._download_file("https://ollama.com/download/OllamaSetup.exe", temp_installer, "Ollama for Windows")
                self._log("[*] Executing silent installation of Ollama (OllamaSetup.exe /silent)...")
                res = subprocess.run([str(temp_installer), "/silent"], check=True)
                self._log("[+] Ollama installer finished.")
                time.sleep(3)
                
                # Add default path to current environment
                ollama_dir = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
                if ollama_dir.exists():
                    os.environ["PATH"] = f"{ollama_dir};" + os.environ.get("PATH", "")
                
                ollama_bin = self._find_ollama_binary()
            except Exception as e:
                self._log(f"[!] Error installing Ollama automatically: {e}")
                self._log("[!] Please install Ollama manually from https://ollama.com")
                return

        if not ollama_bin:
            self._log("[!] Could not detect ollama.exe after installation.")
            return

        self._log(f"[+] Active Ollama executable: {ollama_bin}")

        # Ensure service is running
        if not self._ensure_ollama_service(ollama_bin):
            self._log("[!] Warning: Ollama local service did not respond on port 11434.")

        # Pull chosen base model
        base_model = self.local_model.get().strip() or "qwen2.5:1.5b"
        self._log(f"[*] Pulling local model '{base_model}' via Ollama...")
        self._log("[*] (Streaming download & layer verification...)")

        try:
            creation_flags = 0x08000000 if os.name == 'nt' else 0
            pull_proc = subprocess.Popen(
                [ollama_bin, "pull", base_model],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=creation_flags
            )
            for line in iter(pull_proc.stdout.readline, ''):
                l = line.strip()
                if l and any(k in l.lower() for k in ("pulling", "downloading", "verifying", "writing", "success")):
                    self._log(f"    {l}")
            pull_proc.stdout.close()
            pull_proc.wait()

            if pull_proc.returncode == 0:
                self._log(f"[+] Model '{base_model}' pulled successfully!")
            else:
                self._log(f"[!] Ollama pull exited with code: {pull_proc.returncode}")
        except Exception as e:
            self._log(f"[!] Error while pulling {base_model}: {e}")

        # Build chloe:latest Persona from Modelfile
        try:
            self._log("[*] Building and registering 'chloe:latest' persona in Ollama...")
            modelfile_path = dest / "Modelfile.installer"
            modelfile_content = (
                f"FROM {base_model}\n\n"
                'SYSTEM """You are Chloe, an elite, ultra-low latency personal AI assistant built exclusively for Abhishek.\n'
                "You continuously learn and adapt from Abhishek's habits, preferences, and commands.\n"
                'Always respond with clarity, respect, and natural conversational speech."""\n\n'
                "PARAMETER temperature 0.3\n"
                "PARAMETER top_p 0.9\n"
            )
            with open(modelfile_path, "w", encoding="utf-8") as mf:
                mf.write(modelfile_content)

            create_proc = subprocess.run(
                [ollama_bin, "create", "chloe:latest", "-f", str(modelfile_path)],
                capture_output=True,
                text=True,
                creationflags=0x08000000 if os.name == 'nt' else 0
            )
            if create_proc.returncode == 0:
                self._log("[+] Successfully configured 'chloe:latest' resident persona in Ollama!")
            else:
                self._log(f"[!] Ollama create output: {create_proc.stderr or create_proc.stdout}")

            if modelfile_path.exists():
                modelfile_path.unlink()
        except Exception as e:
            self._log(f"[!] Warning configuring chloe:latest persona: {e}")

    def _run_installation(self):
        """Executes installation, directory creation, config writing, Ollama setup, and shortcut creation."""
        dest = Path(self.install_dir.get())
        
        steps = [
            ("Creating destination directory structure...", 15),
            ("Writing environment & configuration...", 35),
            ("Initializing Continuous Learning databases...", 50),
            ("Configuring Ollama & Local AI Engine...", 70),
            ("Deploying Windows shortcuts...", 85),
            ("Finalizing deployment...", 100)
        ]

        for desc, pct in steps:
            self.lbl_status.config(text=desc)
            self.progress_bar["value"] = pct
            self._log(f"[*] {desc}")

            if pct == 15:
                os.makedirs(dest / "data" / "chroma_db", exist_ok=True)
                os.makedirs(dest / "data" / "memory_chroma_db", exist_ok=True)
                os.makedirs(dest / "data" / "training_datasets", exist_ok=True)
                os.makedirs(dest / "data" / "vault", exist_ok=True)
                os.makedirs(dest / "data" / "logs", exist_ok=True)
                
                # Check for embedded or local payload zip
                payload_zip = None
                if getattr(sys, "frozen", False):
                    p_frozen = Path(sys._MEIPASS) / "chloe_payload.zip"
                    if p_frozen.exists():
                        payload_zip = p_frozen
                if not payload_zip:
                    p_local = INSTALLER_DIR / "chloe_payload.zip"
                    if p_local.exists():
                        payload_zip = p_local
                if not payload_zip:
                    p_exe_dir = Path(sys.executable).parent / "chloe_payload.zip"
                    if p_exe_dir.exists():
                        payload_zip = p_exe_dir

                if payload_zip and payload_zip.exists():
                    self._log(f"[*] Unpacking standalone bundle from {payload_zip.name}...")
                    import zipfile
                    with zipfile.ZipFile(payload_zip, 'r') as z:
                        z.extractall(dest)
                    self._log(f"[+] Extracted full standalone runtime to: {dest}")
                else:
                    # Fallback to local source copy
                    if dest != PROJECT_ROOT:
                        if (PROJECT_ROOT / "backend").exists():
                            shutil.copytree(PROJECT_ROOT / "backend", dest / "backend", dirs_exist_ok=True)
                        if (PROJECT_ROOT / "run.py").exists():
                            shutil.copy2(PROJECT_ROOT / "run.py", dest / "run.py")
                        if (PROJECT_ROOT / "run.bat").exists():
                            shutil.copy2(PROJECT_ROOT / "run.bat", dest / "run.bat")

            elif pct == 35:
                # Write .env configuration
                base_model = self.local_model.get().strip() or "qwen2.5:1.5b"
                env_lines = [
                    f"DEFAULT_MODE={self.operating_mode.get()}",
                    f"GROQ_API_KEY={self.groq_key.get()}",
                    f"GEMINI_API_KEY={self.gemini_key.get()}",
                    f"GROQ_LLM_MODEL=qwen/qwen3.8-27b",
                    f"GEMINI_MODEL=gemini-3.6-flash",
                    f"DEFAULT_TTS_VOICE={self.default_voice.get()}",
                    f"HOST=0.0.0.0",
                    f"PORT=8000",
                    f"OLLAMA_HOST=http://localhost:11434",
                    f"OLLAMA_MODEL=chloe:latest",
                    f"OLLAMA_MODEL_OFFLINE={base_model}"
                ]
                content_env = "\n".join(env_lines) + "\n"
                
                with open(dest / ".env", "w", encoding="utf-8") as f:
                    f.write(content_env)
                if (dest / "backend").exists():
                    with open(dest / "backend" / ".env", "w", encoding="utf-8") as f:
                        f.write(content_env)
                self._log(f"[+] Configuration written to: {dest / '.env'}")

            elif pct == 70:
                # Setup Ollama & Local Models if user enabled option
                if self.install_ollama.get():
                    self._setup_ollama_local(dest)
                else:
                    self._log("[*] Skipping Ollama setup (unselected by user).")

            elif pct == 85:
                # Create shortcuts
                try:
                    if str(INSTALLER_DIR) not in sys.path:
                        sys.path.insert(0, str(INSTALLER_DIR))
                    from create_shortcuts import setup_all_shortcuts
                    setup_all_shortcuts(
                        install_dir=str(dest),
                        create_desktop=self.create_desktop_shortcut.get(),
                        create_start_menu=self.create_start_menu_shortcut.get(),
                        create_startup=self.launch_on_startup.get()
                    )
                    self._log("[+] Windows Desktop & Start Menu shortcuts successfully created.")
                except Exception as e:
                    self._log(f"[!] Shortcut deployment note: {e}")

            time.sleep(0.3)

        self.after(500, lambda: self._show_page(5))

    def _finish_installer(self):
        """Finishes wizard and optionally launches Chloe."""
        if self.launch_after_install.get():
            dest = Path(self.install_dir.get())
            chloe_exe = dest / "Chloe.exe"
            run_bat = dest / "run.bat"
            run_py = dest / "run.py"

            if chloe_exe.exists():
                subprocess.Popen([str(chloe_exe)], cwd=str(dest))
            elif run_bat.exists():
                subprocess.Popen([str(run_bat)], cwd=str(dest), shell=True)
            elif run_py.exists():
                subprocess.Popen([sys.executable, str(run_py)], cwd=str(dest))

            import webbrowser
            webbrowser.open("http://localhost:8000")
        self.destroy()

if __name__ == "__main__":
    app = ChloeSetupWizard()
    app.mainloop()
