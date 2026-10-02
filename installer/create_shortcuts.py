"""
Project Chloe - Windows Shortcut & Shell Integration Utility
Creates Desktop, Start Menu, and Windows Startup shortcuts (.lnk).
"""

import os
import sys
from pathlib import Path

def create_windows_shortcut(target_path: str, shortcut_path: str, description: str = "Project Chloe - AI Assistant", icon_path: str = None, work_dir: str = None):
    """Creates a Windows .lnk shortcut using WScript.Shell COM object."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.TargetPath = str(target_path)
        shortcut.WorkingDirectory = str(work_dir or Path(target_path).parent)
        shortcut.Description = description
        if icon_path and os.path.exists(icon_path):
            shortcut.IconLocation = str(icon_path)
        shortcut.save()
        print(f"[+] Created shortcut: {shortcut_path}")
        return True
    except Exception as e:
        print(f"[!] Win32 COM shortcut creation failed ({e}), falling back to PowerShell...")
        try:
            import subprocess
            ps_script = f"""
            $WshShell = New-Object -comObject WScript.Shell
            $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
            $Shortcut.TargetPath = "{target_path}"
            $Shortcut.WorkingDirectory = "{work_dir or Path(target_path).parent}"
            $Shortcut.Description = "{description}"
            """
            if icon_path and os.path.exists(icon_path):
                ps_script += f'$Shortcut.IconLocation = "{icon_path}"\n'
            ps_script += "$Shortcut.Save()"
            
            subprocess.run(["powershell", "-Command", ps_script], check=True, capture_output=True)
            print(f"[+] Created shortcut via PowerShell: {shortcut_path}")
            return True
        except Exception as e2:
            print(f"[!] Failed to create shortcut: {e2}")
            return False

def setup_all_shortcuts(install_dir: str, create_desktop: bool = True, create_start_menu: bool = True, create_startup: bool = False):
    """Deploys shortcuts across Windows Desktop, Start Menu, and Startup."""
    install_path = Path(install_dir)
    target_exe = install_path / "run.bat"
    if not target_exe.exists():
        target_exe = install_path / "Chloe.exe"
    
    icon_file = install_path / "backend" / "app" / "static" / "favicon.ico"
    if not icon_file.exists():
        icon_file = None

    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    
    # 1. Desktop Shortcut
    if create_desktop:
        desktop_dir = user_profile / "Desktop"
        if desktop_dir.exists():
            create_windows_shortcut(
                target_path=str(target_exe),
                shortcut_path=str(desktop_dir / "Project Chloe.lnk"),
                description="Launch Project Chloe AI Assistant",
                icon_path=str(icon_file) if icon_file else None,
                work_dir=str(install_path)
            )

    # 2. Start Menu Shortcut
    if create_start_menu:
        start_menu_dir = user_profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Project Chloe"
        start_menu_dir.mkdir(parents=True, exist_ok=True)
        create_windows_shortcut(
            target_path=str(target_exe),
            shortcut_path=str(start_menu_dir / "Project Chloe.lnk"),
            description="Launch Project Chloe AI Assistant",
            icon_path=str(icon_file) if icon_file else None,
            work_dir=str(install_path)
        )

    # 3. Startup Shortcut
    if create_startup:
        startup_dir = user_profile / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if startup_dir.exists():
            create_windows_shortcut(
                target_path=str(target_exe),
                shortcut_path=str(startup_dir / "Project Chloe.lnk"),
                description="Auto-start Project Chloe on Boot",
                icon_path=str(icon_file) if icon_file else None,
                work_dir=str(install_path)
            )

if __name__ == "__main__":
    setup_all_shortcuts(r"d:\Chloe", create_desktop=True, create_start_menu=True)
