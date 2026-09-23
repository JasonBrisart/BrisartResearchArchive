from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import datetime
import hashlib
import io
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import webbrowser
import zipfile

from core.constants import (
    APP_NAME,
    APP_VERSION,
    EXPORTS_DIRNAME,
    RELEASE_TAG_PREFIX,
    RELEASES_LIST_URL,
    RELEASES_URL,
    STAGED_EXE_FILENAME,
)
from services.storage import application_dir

UPDATES_DIRNAME = "updates"
BACKUPS_DIRNAME = "backups"
PROTECTED_NAMES = {UPDATES_DIRNAME, EXPORTS_DIRNAME, "__pycache__", ".git", "download.zip"}


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


@dataclass(slots=True)
class UpdateInfo:
    update_available: bool
    current_version: str
    latest_version: str
    message: str
    release_url: str
    download_url: str = ""
    asset_kind: str = "zip"
    asset_digest: str = ""


@dataclass(slots=True)
class InstallResult:
    backup_dir: Path
    staged_dir: Path
    applied_files: tuple[Path, ...]
    restart_required: bool = True


def normalize_version(value: str) -> tuple[int, ...]:
    cleaned = "".join(c for c in value if c.isdigit() or c == ".")
    parts = [int(p) for p in cleaned.split(".") if p.strip().isdigit()]
    if not parts:
        return (0,)
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    return normalize_version(latest) > normalize_version(current)


def version_slug(value: str) -> str:
    slug = "".join(c for c in value if c.isalnum() or c in {".", "-", "_"})
    return slug or "latest"


def strip_release_tag_prefix(tag_name: str, tag_prefix: str = RELEASE_TAG_PREFIX) -> str:
    if tag_name.startswith(tag_prefix):
        return tag_name[len(tag_prefix):]
    return tag_name


def find_latest_release_payload(releases: list[dict], tag_prefix: str) -> dict | None:
    for release in releases:
        tag_name = release.get("tag_name") or ""
        if tag_name.startswith(tag_prefix):
            return release
    return None


def resolve_asset(payload: dict) -> tuple[str, str, str]:
    assets = payload.get("assets") or []
    if is_frozen():
        for asset in assets:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe"):
                return asset.get("browser_download_url") or "", "exe", asset.get("digest") or ""
        return "", "none", ""
    for asset in assets:
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip"):
            return asset.get("browser_download_url") or "", "zip", asset.get("digest") or ""
    return "", "none", ""


def check_for_updates(timeout_seconds: int = 6) -> UpdateInfo:
    try:
        request = urllib.request.Request(RELEASES_LIST_URL, headers={"User-Agent": APP_NAME.replace(" ", "")})
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            releases = json.loads(response.read().decode("utf-8"))
        payload = find_latest_release_payload(releases, RELEASE_TAG_PREFIX)
        if payload is None:
            return UpdateInfo(
                update_available=False, current_version=APP_VERSION, latest_version=APP_VERSION,
                message="No Project Context Helper release was found in the BrisartDevTools releases list.",
                release_url=RELEASES_URL,
            )
        latest_version_raw = payload.get("tag_name") or payload.get("name") or APP_VERSION
        latest_version = strip_release_tag_prefix(latest_version_raw)
        release_url = payload.get("html_url") or RELEASES_URL
        download_url, asset_kind, asset_digest = resolve_asset(payload)
        if not is_newer_version(latest_version, APP_VERSION):
            return UpdateInfo(
                update_available=False, current_version=APP_VERSION, latest_version=latest_version,
                message=f"You are running the latest version ({APP_VERSION}).", release_url=release_url,
                download_url=download_url, asset_kind=asset_kind, asset_digest=asset_digest,
            )
        if asset_kind == "none":
            mode_note = (
                "this build is a compiled executable, so it can only apply a .exe release asset"
                if is_frozen() else
                "this is running in script/dev mode, so it can only apply a packaged .zip release asset"
            )
            return UpdateInfo(
                update_available=True, current_version=APP_VERSION, latest_version=latest_version,
                message=f"Update available: {latest_version} (current: {APP_VERSION}), but no compatible download was found for this run mode — {mode_note}.",
                release_url=release_url, download_url="", asset_kind="none", asset_digest="",
            )
        return UpdateInfo(
            update_available=True, current_version=APP_VERSION, latest_version=latest_version,
            message=f"Update available: {latest_version} (current: {APP_VERSION})", release_url=release_url,
            download_url=download_url, asset_kind=asset_kind, asset_digest=asset_digest,
        )
    except urllib.error.URLError as exc:
        return UpdateInfo(
            update_available=False, current_version=APP_VERSION, latest_version=APP_VERSION,
            message=f"Update check failed: {exc}", release_url=RELEASES_URL,
        )
    except Exception as exc:
        return UpdateInfo(
            update_available=False, current_version=APP_VERSION, latest_version=APP_VERSION,
            message=f"Update check failed: {exc}", release_url=RELEASES_URL,
        )


def verify_digest(data: bytes, digest: str) -> None:
    if not digest or ":" not in digest:
        return
    algorithm, _, expected = digest.partition(":")
    algorithm = algorithm.lower().strip()
    expected = expected.lower().strip()
    if algorithm != "sha256":
        return
    actual = hashlib.sha256(data).hexdigest().lower()
    if actual != expected:
        raise ValueError(f"Downloaded update failed checksum verification. Expected {expected}, got {actual}.")


def download_update(info: UpdateInfo, dest_dir: Path | None = None, timeout_seconds: int = 60) -> Path:
    """
    Bugfix (v3.1.2): a downloaded archive that failed to extract
    (zipfile.BadZipFile -- e.g. from a truncated download, a network
    hiccup, or a CDN serving an error page instead of the real asset)
    was previously caught and silently ignored (`except
    zipfile.BadZipFile: pass`), after which this function still
    returned dest_dir as if everything had succeeded. Downstream,
    apply_staged_update() -> find_release_root() would find nothing
    but the raw download.zip sitting in that folder, and
    apply_extracted_update() explicitly skips a file literally named
    "download.zip" -- so the entire update would silently apply ZERO
    files, while every caller (both the CLI and the GUI) reported
    "Update Installed" / "Files updated: 0" as if nothing had gone
    wrong. A corrupted download attempting to overwrite the running
    application now raises a clear, descriptive error instead of
    completing as a silent no-op.
    """
    if not info.download_url:
        raise ValueError("No download URL is available for this release.")
    if dest_dir is None:
        dest_dir = application_dir() / UPDATES_DIRNAME / f"v{version_slug(info.latest_version)}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(info.download_url, headers={"User-Agent": APP_NAME.replace(" ", "")})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
    if info.asset_digest:
        verify_digest(data, info.asset_digest)
    archive_path = dest_dir / "download.zip"
    archive_path.write_bytes(data)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            archive.extractall(dest_dir)
    except zipfile.BadZipFile as exc:
        raise ValueError(
            f"The downloaded update from {info.download_url} was not a valid "
            f"zip archive ({exc}). This can happen if the download was "
            "interrupted or corrupted in transit; no files were changed. "
            "Please try checking for updates again."
        ) from exc
    return dest_dir


def find_release_root(extract_dir: Path) -> Path:
    candidates = [e for e in extract_dir.iterdir() if e.name != "download.zip"]
    if len(candidates) == 1 and candidates[0].is_dir():
        return candidates[0]
    return extract_dir


def backup_application(app_dir: Path, current_version: str, backup_root: Path | None = None) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_root is None:
        backup_root = app_dir / UPDATES_DIRNAME / BACKUPS_DIRNAME
    backup_dir = backup_root / f"v{version_slug(current_version)}_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for entry in app_dir.iterdir():
        if entry.name in PROTECTED_NAMES:
            continue
        destination = backup_dir / entry.name
        if entry.is_dir():
            shutil.copytree(entry, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(entry, destination)
    return backup_dir


def apply_extracted_update(source_root: Path, app_dir: Path) -> list[Path]:
    applied: list[Path] = []
    for source_path in sorted(source_root.rglob("*")):
        if not source_path.is_file():
            continue
        relative = source_path.relative_to(source_root)
        if relative.parts and relative.parts[0] in PROTECTED_NAMES:
            continue
        if "__pycache__" in relative.parts:
            continue
        if source_path.name == "download.zip":
            continue
        destination = app_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination)
        applied.append(destination)
    return applied


def apply_staged_update(staged_dir: Path, app_dir: Path | None = None, current_version: str = APP_VERSION) -> InstallResult:
    if app_dir is None:
        app_dir = application_dir()
    source_root = find_release_root(staged_dir)
    backup_dir = backup_application(app_dir, current_version)
    applied = apply_extracted_update(source_root, app_dir)
    return InstallResult(backup_dir=backup_dir, staged_dir=staged_dir, applied_files=tuple(applied))


def install_update(info: UpdateInfo, app_dir: Path | None = None, dest_dir: Path | None = None, timeout_seconds: int = 60) -> InstallResult:
    if info.asset_kind != "zip":
        raise ValueError(
            f"install_update() applies source-file updates from a packaged .zip asset and cannot be used for asset_kind='{info.asset_kind}'. "
            "Use stage_exe_update() and apply_exe_update() for an 'exe' asset, or skip entirely for 'none'."
        )
    staged_dir = download_update(info, dest_dir=dest_dir, timeout_seconds=timeout_seconds)
    return apply_staged_update(staged_dir, app_dir=app_dir, current_version=APP_VERSION)


def backup_exe(target_exe_path: Path, current_version: str, backup_root: Path | None = None) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if backup_root is None:
        backup_root = target_exe_path.parent / UPDATES_DIRNAME / BACKUPS_DIRNAME
    backup_root.mkdir(parents=True, exist_ok=True)
    backup_path = backup_root / f"{target_exe_path.stem}_v{version_slug(current_version)}_{stamp}{target_exe_path.suffix}"
    shutil.copy2(target_exe_path, backup_path)
    return backup_path


def stage_exe_update(info: UpdateInfo, dest_dir: Path | None = None, timeout_seconds: int = 180) -> Path:
    if not info.download_url:
        raise ValueError("No download URL is available for this release.")
    if dest_dir is None:
        dest_dir = application_dir() / UPDATES_DIRNAME / f"v{version_slug(info.latest_version)}"
    dest_dir.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(info.download_url, headers={"User-Agent": APP_NAME.replace(" ", "")})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        data = response.read()
    if info.asset_digest:
        verify_digest(data, info.asset_digest)
    staged_path = dest_dir / STAGED_EXE_FILENAME
    staged_path.write_bytes(data)
    return staged_path


def _escape_batch_path(value: str) -> str:
    """
    Escape a filesystem path for safe embedding inside a Windows batch
    (.bat) script by doubling every literal percent sign.
    """
    return value.replace("%", "%%")


def build_apply_batch_script(new_exe_path: Path, target_exe_path: Path, relaunch: bool = True) -> Path:
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
    subprocess.Popen(["cmd.exe", "/c", str(script_path)], creationflags=detached_process | create_new_process_group, close_fds=True)


def apply_exe_update(staged_exe_path: Path, target_exe_path: Path | None = None, current_version: str = APP_VERSION, relaunch: bool = True) -> Path:
    if target_exe_path is None:
        if not is_frozen():
            raise RuntimeError("apply_exe_update() only applies when running as a frozen (PyInstaller) executable.")
        target_exe_path = Path(sys.executable).resolve()
    backup_exe(target_exe_path, current_version)
    script_path = build_apply_batch_script(staged_exe_path.resolve(), target_exe_path, relaunch=relaunch)
    launch_apply_script(script_path)
    return script_path


def open_releases_page(url: str = RELEASES_URL) -> None:
    webbrowser.open(url)
