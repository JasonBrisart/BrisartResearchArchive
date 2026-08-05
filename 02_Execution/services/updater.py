"""
Brisart Research Archive updater (single-file consolidation).
Downloads only. Never extracts, installs, or overwrites app files.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ============================================================
# Shared constants
# ============================================================

GITHUB_OWNER = "JasonBrisart"
GITHUB_REPO = "BrisartResearchArchive"
GITHUB_BRANCH = "main"
REMOTE_VERSION_PATH = "02_Execution/version.txt"
EXECUTION_DIR = Path(__file__).resolve().parents[1]
LOCAL_VERSION_FILE = EXECUTION_DIR / "version.txt"
APP_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "Brisart Research Archive"
UPDATES_DIR = APP_DIR / "updates"
REMOTE_VERSION_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}/{REMOTE_VERSION_PATH}"
)
REMOTE_ZIP_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/archive/refs/heads/{GITHUB_BRANCH}.zip"
ALLOWED_REMOTE_HOSTS = {"github.com", "codeload.github.com", "raw.githubusercontent.com"}
USER_AGENT = "BrisartResearchArchive-Updater/1.0"
VERSION_PATTERN = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:[\s\-].*)?$")
VERSION_TIMEOUT_SECONDS = 15
DOWNLOAD_TIMEOUT_SECONDS = 120
MAX_VERSION_RESPONSE_BYTES = 1024
MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
MAX_ZIP_MEMBERS = 25_000
MAX_UNCOMPRESSED_ZIP_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 250.0


# ============================================================
# Versioning
# ============================================================

def normalize_version(version_text: Any) -> tuple[int, int, int]:
    value = str(version_text).strip()
    match = VERSION_PATTERN.fullmatch(value)
    if match is None:
        raise ValueError(f"Version must use MAJOR.MINOR.PATCH format: {value!r}")
    return tuple(int(component) for component in match.groups())


def canonical_version(version_text: Any) -> str:
    major, minor, patch = normalize_version(version_text)
    return f"{major}.{minor}.{patch}"


def safe_version_filename(version_text: Any) -> str:
    return canonical_version(version_text)


def is_remote_newer(remote_version: Any, local_version: Any) -> bool:
    return normalize_version(remote_version) > normalize_version(local_version)


def _default_emit(line: str) -> None:
    print(line)


def read_local_version(emit: Callable[[str], None] = _default_emit) -> str:
    if not LOCAL_VERSION_FILE.is_file():
        emit("Local version metadata was not found. Using 0.0.0.")
        return "0.0.0"
    try:
        value = LOCAL_VERSION_FILE.read_text(encoding="utf-8-sig").strip()
        return canonical_version(value)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        emit(f"Local version metadata is invalid. Using 0.0.0: {exc}")
        return "0.0.0"


# ============================================================
# Archives (ZIP validation)
# ============================================================

def file_has_zip_signature(path: Path) -> bool:
    path = Path(path)
    try:
        with open(path, "rb") as file:
            signature = file.read(4)
    except OSError:
        return False
    return signature in {b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"}


def zip_member_is_safe(member_name: str) -> bool:
    normalized = str(member_name).replace("\\", "/")
    if not normalized:
        return False
    if normalized.startswith("/"):
        return False
    if "\x00" in normalized:
        return False
    path_parts = [part for part in normalized.split("/") if part]
    if not path_parts:
        return False
    if any(part in {".", ".."} for part in path_parts):
        return False
    first_part = path_parts[0]
    if len(first_part) >= 2 and first_part[1] == ":":
        return False
    return True


def validate_zip_archive(path: Path) -> None:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ZIP file was not found: {path}")
    file_size = path.stat().st_size
    if file_size < 1:
        raise ValueError("The downloaded update was empty.")
    if file_size > MAX_DOWNLOAD_BYTES:
        raise ValueError(f"The downloaded update exceeds the maximum allowed size of {MAX_DOWNLOAD_BYTES:,} bytes.")
    if not file_has_zip_signature(path):
        raise ValueError("The downloaded file does not have a valid ZIP signature.")
    if not zipfile.is_zipfile(path):
        raise ValueError("The downloaded file is not a readable ZIP archive.")
    with zipfile.ZipFile(path, "r") as archive:
        members = archive.infolist()
        if not members:
            raise ValueError("The downloaded ZIP contains no files.")
        if len(members) > MAX_ZIP_MEMBERS:
            raise ValueError(f"The downloaded ZIP contains too many entries: {len(members):,}")
        total_uncompressed_bytes = 0
        for member in members:
            if not zip_member_is_safe(member.filename):
                raise ValueError(f"The downloaded ZIP contains an unsafe path: {member.filename!r}")
            total_uncompressed_bytes += member.file_size
            if total_uncompressed_bytes > MAX_UNCOMPRESSED_ZIP_BYTES:
                raise ValueError("The downloaded ZIP expands beyond the allowed uncompressed-size limit.")
            if member.file_size > 0 and member.compress_size == 0 and not member.is_dir():
                raise ValueError(f"The downloaded ZIP contains an invalid compressed entry: {member.filename!r}")
            if member.compress_size > 0 and member.file_size > 0:
                compression_ratio = member.file_size / member.compress_size
                if compression_ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError(f"The downloaded ZIP contains an entry with an excessive compression ratio: {member.filename!r}")
        corrupted_member = archive.testzip()
        if corrupted_member is not None:
            raise ValueError(f"ZIP integrity validation failed for: {corrupted_member}")


# ============================================================
# HTTP
# ============================================================

def validate_remote_url(url: str, *, allowed_hosts: set[str] | None = None) -> str:
    value = str(url).strip()
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme.casefold() != "https":
        raise ValueError("Update URLs must use HTTPS.")
    hostname = (parsed.hostname or "").casefold()
    hosts = ALLOWED_REMOTE_HOSTS if allowed_hosts is None else {str(host).casefold() for host in allowed_hosts}
    if hostname not in hosts:
        raise ValueError(f"Update URL host is not allowed: {hostname or '<missing>'}")
    if parsed.username or parsed.password:
        raise ValueError("Update URLs cannot contain credentials.")
    return value


def response_final_url(response: Any) -> str:
    getter = getattr(response, "geturl", None)
    if not callable(getter):
        raise ValueError("The update response did not expose a final URL.")
    return validate_remote_url(getter())


def build_request(url: str, accept: str) -> urllib.request.Request:
    validated_url = validate_remote_url(url)
    return urllib.request.Request(
        validated_url,
        headers={"User-Agent": USER_AGENT, "Accept": str(accept), "Cache-Control": "no-cache"},
        method="GET",
    )


def read_bounded_response(response: Any, maximum_bytes: int) -> bytes:
    if maximum_bytes < 1:
        raise ValueError("maximum_bytes must be positive.")
    declared_length = (response.headers.get("Content-Length", "") or "").strip()
    if declared_length:
        try:
            declared_bytes = int(declared_length)
        except ValueError:
            declared_bytes = -1
        if declared_bytes > maximum_bytes:
            raise ValueError(f"Remote response exceeds the allowed size of {maximum_bytes:,} bytes.")
    data = response.read(maximum_bytes + 1)
    if len(data) > maximum_bytes:
        raise ValueError(f"Remote response exceeded the allowed size of {maximum_bytes:,} bytes.")
    return data


def fetch_remote_version() -> str:
    request = build_request(REMOTE_VERSION_URL, "text/plain")
    with urllib.request.urlopen(request, timeout=VERSION_TIMEOUT_SECONDS) as response:
        response_final_url(response)
        raw = read_bounded_response(response, MAX_VERSION_RESPONSE_BYTES)
    value = raw.decode("utf-8-sig").strip()
    if not value:
        raise ValueError("Remote version metadata was empty.")
    return canonical_version(value)


def response_is_zip(response: Any) -> bool:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
    allowed_types = {"", "application/zip", "application/x-zip-compressed", "application/octet-stream"}
    return content_type in allowed_types


# ============================================================
# Cache
# ============================================================

def ensure_updates_directory() -> Path:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    return UPDATES_DIR


def update_output_file(remote_version: Any) -> Path:
    version = safe_version_filename(remote_version)
    return UPDATES_DIR / f"BrisartResearchArchive_{version}.zip"


def remove_file_safely(path: Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def existing_update_is_valid(path: Path) -> bool:
    try:
        validate_zip_archive(path)
        return True
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return False


def cleanup_partial_downloads() -> int:
    if not UPDATES_DIR.is_dir():
        return 0
    removed_count = 0
    for path in UPDATES_DIR.glob("*.zip.part"):
        try:
            path.unlink()
            removed_count += 1
        except OSError:
            pass
    return removed_count


def copy_update_package(source: Path, destination: Path) -> Path:
    source = Path(source)
    destination = Path(destination)
    validate_zip_archive(source)
    if destination.exists() and destination.is_dir():
        destination = destination / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    validate_zip_archive(destination)
    return destination


# ============================================================
# Download
# ============================================================

def download_latest_zip(remote_version: Any, emit: Callable[[str], None] = _default_emit) -> Path:
    version = canonical_version(remote_version)
    ensure_updates_directory()
    output_file = update_output_file(version)
    if output_file.exists():
        if existing_update_is_valid(output_file):
            emit("Update already downloaded:")
            emit(str(output_file))
            return output_file
        emit("Existing update file is invalid and will be replaced:")
        emit(str(output_file))
        remove_file_safely(output_file)

    request = build_request(REMOTE_ZIP_URL, "application/zip,application/octet-stream")
    emit("Downloading newest GitHub version...")
    emit(f"Source: {REMOTE_ZIP_URL}")
    emit(f"Destination: {output_file}")

    temporary_path: Path | None = None
    total_bytes = 0
    try:
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix=output_file.stem + "_", suffix=".zip.part", dir=UPDATES_DIR
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)
        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            response_final_url(response)
            if not response_is_zip(response):
                content_type = response.headers.get("Content-Type", "unknown")
                raise ValueError(f"Update server returned an unexpected content type: {content_type}")
            declared_length = (response.headers.get("Content-Length", "") or "").strip()
            if declared_length:
                try:
                    declared_bytes = int(declared_length)
                except ValueError:
                    declared_bytes = -1
                if declared_bytes > MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"The update package exceeds the maximum allowed size of {MAX_DOWNLOAD_BYTES:,} bytes.")
            with open(temporary_path, "wb") as file:
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > MAX_DOWNLOAD_BYTES:
                        raise ValueError(f"The update download exceeded the maximum allowed size of {MAX_DOWNLOAD_BYTES:,} bytes.")
                    file.write(chunk)
                file.flush()
                try:
                    os.fsync(file.fileno())
                except OSError:
                    pass
        if total_bytes < 1:
            raise ValueError("The downloaded update was empty.")
        validate_zip_archive(temporary_path)
        temporary_path.replace(output_file)
        temporary_path = None
    except Exception:
        if temporary_path is not None:
            remove_file_safely(temporary_path)
        raise
    emit("Download complete.")
    emit(f"Bytes downloaded: {total_bytes}")
    emit(f"Saved to: {output_file}")
    return output_file


# ============================================================
# Results
# ============================================================

def build_update_result(
    *, status: str, local_version: str, remote_version: str = "",
    downloaded_file: Path | None = None, message: str = "",
) -> dict[str, Any]:
    return {
        "status": str(status),
        "local_version": str(local_version),
        "remote_version": str(remote_version),
        "downloaded_file": str(downloaded_file) if downloaded_file is not None else "",
        "message": str(message),
    }


# ============================================================
# Service (orchestration)
# ============================================================

def startup_update_check(emit: Callable[[str], None] = _default_emit) -> dict[str, Any]:
    """
    Run one update check.

    `emit` receives every human-readable status line, in order. The
    default (print to real stdout) is exactly the previous behavior for
    direct/CLI callers. run_update_check() (the GUI-facing wrapper)
    passes a thread-safe collector instead of relying on
    contextlib.redirect_stdout - which swaps sys.stdout process-wide,
    not per-thread, so a background update-check thread using it could
    silently swallow print() output from completely unrelated code
    running on the main thread or any other thread at the same time,
    and could corrupt the report shown to the user with unrelated text.
    """
    emit("")
    emit("Checking for updates...")
    local_version = read_local_version(emit)
    try:
        cleanup_partial_downloads()
        remote_version = fetch_remote_version()
        emit(f"Local Version:  {local_version}")
        emit(f"GitHub Version: {remote_version}")
        emit("")
        emit("Remote version source:")
        emit(REMOTE_VERSION_URL)
        emit("")
        emit("Local version file:")
        emit(str(LOCAL_VERSION_FILE))
        emit("")
        emit("Update cache directory:")
        emit(str(UPDATES_DIR))
        if is_remote_newer(remote_version, local_version):
            emit("")
            emit("Update found.")
            downloaded_file = download_latest_zip(remote_version, emit)
            emit("")
            emit("Update package downloaded.")
            emit(str(downloaded_file))
            emit("")
            emit("Install/apply remains manual.")
            return build_update_result(
                status="downloaded", local_version=local_version, remote_version=remote_version,
                downloaded_file=downloaded_file,
                message="A newer update package was downloaded. Installation remains manual.",
            )
        emit("")
        if normalize_version(remote_version) == normalize_version(local_version):
            emit("No update found. The installed version is current.")
            status = "current"
            message = "The installed version matches the remote version."
        else:
            emit("No update downloaded. The local version is newer than the remote version.")
            status = "local_newer"
            message = "The local version is newer than the remote version."
        return build_update_result(status=status, local_version=local_version, remote_version=remote_version, message=message)
    except urllib.error.HTTPError as exc:
        emit("")
        emit("Update check failed.")
        emit(f"HTTP Error: {exc.code}")
        emit(f"URL: {exc.url}")
        emit("Verify the repository name, branch, and remote version path.")
        return build_update_result(status="http_error", local_version=local_version, message=f"HTTP Error {exc.code}: {exc.reason}")
    except urllib.error.URLError as exc:
        emit("")
        emit("Update check failed.")
        emit(f"Network error: {exc.reason}")
        return build_update_result(status="network_error", local_version=local_version, message=str(exc.reason))
    except (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        emit("")
        emit("Update check failed.")
        emit(f"{type(exc).__name__}: {exc}")
        return build_update_result(status="validation_error", local_version=local_version, message=f"{type(exc).__name__}: {exc}")
    except Exception as exc:
        emit("")
        emit("Update check failed unexpectedly.")
        emit(f"{type(exc).__name__}: {exc}")
        return build_update_result(status="unexpected_error", local_version=local_version, message=f"{type(exc).__name__}: {exc}")


# ============================================================
# Tkinter integration (UI)
# ============================================================

_update_lock = threading.Lock()


def app_is_alive(app: Any) -> bool:
    try:
        return bool(app.winfo_exists())
    except (AttributeError, tk.TclError):
        return False


def widget_is_alive(widget: Any) -> bool:
    if widget is None:
        return False
    try:
        return bool(widget.winfo_exists())
    except (AttributeError, tk.TclError):
        return False


def schedule_on_ui_thread(app: Any, callback: Callable[[], None]) -> bool:
    if not app_is_alive(app):
        return False
    try:
        app.after(0, callback)
    except (AttributeError, tk.TclError):
        return False
    return True


def update_checks_enabled(app: Any) -> bool:
    variable = getattr(app, "enable_update_checks", None)
    if variable is None:
        return True
    try:
        return bool(variable.get())
    except (AttributeError, tk.TclError):
        return False


def set_status_text(app: Any, message: str) -> None:
    status_variable = getattr(app, "status_text", None)
    if status_variable is None:
        return
    try:
        status_variable.set(str(message))
    except (AttributeError, tk.TclError):
        pass


def find_update_box(app: Any) -> Any | None:
    update_box = getattr(app, "update_box", None)
    if widget_is_alive(update_box):
        return update_box
    show_page = getattr(app, "show_page", None)
    if not callable(show_page):
        return None
    try:
        show_page("System")
    except (AttributeError, tk.TclError):
        return None
    update_box = getattr(app, "update_box", None)
    if widget_is_alive(update_box):
        return update_box
    return None


def set_update_text(app: Any, report: str) -> None:
    if not app_is_alive(app):
        return
    update_box = find_update_box(app)
    if update_box is None:
        return
    try:
        update_box.delete("1.0", "end")
        update_box.insert("end", str(report))
        update_box.see("1.0")
    except tk.TclError:
        return
    set_status_text(app, "Update check complete")


def format_update_result(result: Any, captured_output: str) -> str:
    output = str(captured_output).strip()
    if output:
        return output
    if isinstance(result, dict):
        status = str(result.get("status", "")).strip()
        local_version = str(result.get("local_version", "")).strip()
        remote_version = str(result.get("remote_version", "")).strip()
        downloaded_file = str(result.get("downloaded_file", "")).strip()
        message = str(result.get("message", "")).strip()
        lines: list[str] = []
        if status:
            lines.append(f"Status: {status}")
        if local_version:
            lines.append(f"Local version: {local_version}")
        if remote_version:
            lines.append(f"Remote version: {remote_version}")
        if downloaded_file:
            lines.append(f"Downloaded file: {downloaded_file}")
        if message:
            if lines:
                lines.append("")
            lines.append(message)
        if lines:
            return "\n".join(lines)
    return "Update check completed."


def run_update_check() -> str:
    """
    GUI-facing entry point, safe to call from a background thread.

    Previously this used contextlib.redirect_stdout(output_buffer)
    around startup_update_check(). redirect_stdout swaps sys.stdout for
    the whole process, not just the calling thread - so while an update
    check ran on its background thread, any *other* thread (including
    the main GUI thread) calling print() anywhere else in the app would
    have its output silently captured into this buffer instead of the
    real console, and could corrupt the report text shown to the user
    with unrelated content. Collecting lines via a plain list passed as
    the `emit` callback has the exact same effect for this call's own
    output but is fully thread-safe, since it never touches the shared
    sys.stdout at all.
    """
    collected_lines: list[str] = []

    def _collect_and_print(line: str) -> None:
        collected_lines.append(line)
        print(line)

    try:
        result = startup_update_check(_collect_and_print)
        captured_output = "\n".join(collected_lines).strip()
        return format_update_result(result=result, captured_output=captured_output)
    except Exception as exc:
        captured_output = "\n".join(collected_lines).strip()
        lines = ["Update check failed.", "", f"{type(exc).__name__}: {exc}"]
        if captured_output:
            lines.extend(["", "Updater output before failure:", captured_output])
        return "\n".join(lines)


def check_updates(app: Any) -> None:
    if not app_is_alive(app):
        return
    if not update_checks_enabled(app):
        set_update_text(app, "Update checks are disabled.\n\nNo remote request was made.\nThe Archive will remain on the current local version.")
        return
    if not _update_lock.acquire(blocking=False):
        set_update_text(app, "An update check is already running.\n\nThe existing request will continue.")
        return
    set_status_text(app, "Checking for updates...")

    def worker() -> None:
        try:
            report = run_update_check()
        finally:
            _update_lock.release()
        schedule_on_ui_thread(app, lambda: set_update_text(app, report))

    try:
        thread = threading.Thread(target=worker, name="BrisartUpdateCheck", daemon=True)
        thread.start()
    except Exception:
        _update_lock.release()
        raise


def update_check_is_running() -> bool:
    acquired = _update_lock.acquire(blocking=False)
    if not acquired:
        return True
    _update_lock.release()
    return False


__all__ = [
    "normalize_version", "canonical_version", "safe_version_filename", "is_remote_newer", "read_local_version",
    "file_has_zip_signature", "zip_member_is_safe", "validate_zip_archive",
    "validate_remote_url", "response_final_url", "build_request", "read_bounded_response",
    "fetch_remote_version", "response_is_zip",
    "ensure_updates_directory", "update_output_file", "remove_file_safely", "existing_update_is_valid",
    "cleanup_partial_downloads", "copy_update_package",
    "download_latest_zip", "build_update_result", "startup_update_check",
    "app_is_alive", "widget_is_alive", "schedule_on_ui_thread", "update_checks_enabled", "set_status_text",
    "find_update_box", "set_update_text", "format_update_result", "run_update_check",
    "check_updates", "update_check_is_running",
]
