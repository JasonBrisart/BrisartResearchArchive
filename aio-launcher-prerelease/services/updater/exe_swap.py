"""
services/updater/exe_swap.py

Frozen-executable self-update: a running .exe cannot overwrite itself
while executing, so this backs up the current exe and launches a
detached batch script that waits out the file lock, swaps the new
(already-verified) exe into place, and optionally relaunches it.

Only relevant if this app is ever distributed as a compiled .exe --
harmless and unused when running from source.
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

from services.updater.constants import BACKUPS_DIR, is_frozen
from services.updater.versioning import version_slug


def backup_exe(target_exe_path: Path, current_version: str) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUPS_DIR / f"{target_exe_path.stem}_v{version_slug(current_version)}_{stamp}{target_exe_path.suffix}"
    shutil.copy2(target_exe_path, backup_path)
    return backup_path


def _escape_batch_path(value: str) -> str:
    """Doubles every literal percent sign -- Windows batch treats a bare
    '%' as the start of a variable reference even inside quotes, so an
    install path containing one (a valid Windows filename character,
    e.g. a folder named "50% Done") would otherwise be silently and
    partially substituted by cmd.exe during the exe-swap step."""
    return value.replace("%", "%%")


def build_apply_batch_script(new_exe_path: Path, target_exe_path: Path, relaunch: bool = True) -> Path:
    """A running .exe cannot overwrite itself while executing. This
    generates a small detached batch script that: waits for the current
    process to release its file lock (retrying delete for a few
    seconds), moves the new, already-verified exe into place, and
    optionally relaunches it -- then deletes itself."""
    relaunch_flag = "1" if relaunch else "0"
    new_exe_str = _escape_batch_path(str(new_exe_path))
    target_exe_str = _escape_batch_path(str(target_exe_path))
    script_lines = [
        "@echo off", "setlocal EnableDelayedExpansion",
        f'set "NEWEXE={new_exe_str}"', f'set "TARGET={target_exe_str}"', f'set "RELAUNCH={relaunch_flag}"',
        "set /a attempts=0", ":retry", "set /a attempts+=1", 'del /f /q "%TARGET%" 2>nul',
        'if exist "%TARGET%" (', "    if !attempts! LSS 20 (", "        timeout /t 1 /nobreak >nul",
        "        goto retry", "    ) else (", "        exit /b 1", "    )", ")",
        'move /y "%NEWEXE%" "%TARGET%" >nul', 'if "%RELAUNCH%"=="1" (', '    start "" "%TARGET%"', ")",
        'del /f /q "%~f0"', "",
    ]
    script_path = new_exe_path.parent / "apply_update.bat"
    script_path.write_text("\r\n".join(script_lines), encoding="utf-8")
    return script_path


def launch_apply_script(script_path: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError("Exe self-update is only supported on Windows.")
    detached_process = 0x00000008
    create_new_process_group = 0x00000200
    subprocess.Popen(
        ["cmd.exe", "/c", str(script_path)],
        creationflags=detached_process | create_new_process_group,
        close_fds=True,
    )


def apply_exe_update(verified_exe_path: Path, current_version: str, relaunch: bool = True) -> Path:
    """Only valid when running as a frozen exe. Backs up the current exe,
    launches the swap script, and returns the script path so the caller
    knows to exit immediately afterward (the running process must release
    its own file lock for the swap to succeed)."""
    if not is_frozen():
        raise RuntimeError("apply_exe_update() only applies when running as a frozen (PyInstaller) executable.")
    target_exe_path = Path(sys.executable).resolve()
    backup_exe(target_exe_path, current_version)
    script_path = build_apply_batch_script(verified_exe_path.resolve(), target_exe_path, relaunch=relaunch)
    launch_apply_script(script_path)
    return script_path
