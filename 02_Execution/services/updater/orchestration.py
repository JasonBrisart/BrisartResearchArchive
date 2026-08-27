"""
services/updater/orchestration.py
Ties the registry/download/install pieces together into complete
operations.

  - startup_update_check(emit): check + download-only, never installs
    and never asks anything. Kept for any caller that explicitly wants
    "just tell me if there's something new, don't touch my files and
    don't prompt anyone."

  - check_and_maybe_install(emit, auto_install, confirm_install): the
    single function behind BOTH the "Check Updates" button and the
    automatic startup check. Always checks the registry. What happens
    next depends on `auto_install`:

      * auto_install=True: downloads, verifies, and installs
        immediately. No prompt is ever shown (the checkbox itself was
        the user's confirmation).

      * auto_install=False and `confirm_install` is provided: BEFORE
        downloading anything, calls confirm_install(remote_version) --
        a synchronous, blocking callback the GUI wires up to a Yes/No
        dialog. If it returns True, the release is downloaded,
        verified, and installed. If it returns False, nothing is
        downloaded and status "declined" is returned -- the same
        release will simply be offered again next time (on next
        startup, or the next manual check), since the local version
        file hasn't changed.

      * auto_install=False and `confirm_install` is None: preserves
        the original silent behavior -- downloads and verifies in the
        background, but never installs and never prompts. Status
        "downloaded" is returned. This is what happens today when the
        user has turned off "Notify me about updates" -- no
        interruption, but the app still keeps a verified release ready
        the moment they change their mind.
"""
from __future__ import annotations

import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib import error as urllib_error

from services.updater.constants import is_frozen
from services.updater.download import download_and_verify_release
from services.updater.exe_swap import apply_exe_update
from services.updater.install import apply_zip_update
from services.updater.registry import RegistryEntry, RegistryError, VerificationError, fetch_registry_entry
from services.updater.versioning import canonical_version, default_emit, is_remote_newer, normalize_version, read_local_version


def build_update_result(
    *, status: str, local_version: str, remote_version: str = "",
    downloaded_file: Path | None = None, message: str = "", changelog: str = "",
) -> dict[str, Any]:
    return {
        "status": str(status),
        "local_version": str(local_version),
        "remote_version": str(remote_version),
        "downloaded_file": str(downloaded_file) if downloaded_file is not None else "",
        "message": str(message),
        "changelog": str(changelog),
    }


def _apply_verified_release(
    entry: RegistryEntry, verified_path: Path, local_version: str, remote_version: str,
    emit: Callable[[str], None],
) -> dict[str, Any]:
    """Shared install step: applies an already hash- and
    signature-verified release. Never called on unverified data."""
    if entry.asset_kind == "exe":
        if not is_frozen():
            return build_update_result(
                status="asset_mismatch", local_version=local_version, remote_version=remote_version,
                downloaded_file=verified_path, changelog=entry.changelog,
                message=(
                    "This release is packaged as an .exe, but the application is "
                    "currently running from source. The verified file was downloaded "
                    f"to {verified_path} but was not applied automatically."
                ),
            )
        emit("Applying verified executable update...")
        script_path = apply_exe_update(verified_path, current_version=local_version)
        emit(f"Swap script launched: {script_path}")
        emit("This process will now exit so the new executable can be swapped into place.")
        return build_update_result(
            status="exe_swap_pending", local_version=local_version, remote_version=remote_version,
            downloaded_file=verified_path, changelog=entry.changelog,
            message="Verified update staged. The application will now close and relaunch automatically.",
        )

    if is_frozen():
        return build_update_result(
            status="asset_mismatch", local_version=local_version, remote_version=remote_version,
            downloaded_file=verified_path, changelog=entry.changelog,
            message=(
                "This release is packaged as a source .zip, but the application is "
                "currently running as a compiled executable. The verified file was "
                f"downloaded to {verified_path} but was not applied automatically."
            ),
        )

    emit("Applying verified source update...")
    result = apply_zip_update(verified_path, current_version=local_version)
    emit(f"Backup written to: {result.backup_dir}")
    emit(f"Files updated: {len(result.applied_files)}")
    emit("Restart the application to run the new version.")
    return build_update_result(
        status="installed", local_version=local_version, remote_version=remote_version,
        downloaded_file=verified_path, changelog=entry.changelog,
        message=f"Update installed. Backup: {result.backup_dir}. Files updated: {len(result.applied_files)}. Restart required.",
    )


def _map_exception(exc: Exception, local_version: str) -> dict[str, Any]:
    if isinstance(exc, RegistryError):
        return build_update_result(status="registry_error", local_version=local_version, message=str(exc))
    if isinstance(exc, VerificationError):
        return build_update_result(status="verification_failed", local_version=local_version, message=str(exc))
    if isinstance(exc, urllib_error.HTTPError):
        return build_update_result(status="http_error", local_version=local_version, message=f"HTTP Error {exc.code}: {exc.reason}")
    if isinstance(exc, urllib_error.URLError):
        return build_update_result(status="network_error", local_version=local_version, message=str(exc.reason))
    if isinstance(exc, (OSError, UnicodeDecodeError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile)):
        return build_update_result(status="validation_error", local_version=local_version, message=f"{type(exc).__name__}: {exc}")
    return build_update_result(status="unexpected_error", local_version=local_version, message=f"{type(exc).__name__}: {exc}")


def startup_update_check(emit: Callable[[str], None] = default_emit) -> dict[str, Any]:
    """Check + download-only. Never installs, never prompts. Kept for
    callers that explicitly want a "just tell me" check with zero side
    effects on the application's own files and zero UI interaction."""
    local_version = read_local_version(emit)
    try:
        entry = fetch_registry_entry()
        remote_version = canonical_version(entry.version)
        if is_remote_newer(remote_version, local_version):
            downloaded_file = download_and_verify_release(entry, emit)
            return build_update_result(
                status="downloaded", local_version=local_version, remote_version=remote_version,
                downloaded_file=downloaded_file, changelog=entry.changelog,
                message="A newer, signature-verified update package was downloaded.",
            )
        if normalize_version(remote_version) == normalize_version(local_version):
            status, message = "current", "The installed version matches the registry version."
        else:
            status, message = "local_newer", "The local version is newer than the registry version."
        return build_update_result(status=status, local_version=local_version, remote_version=remote_version, message=message)
    except Exception as exc:
        return _map_exception(exc, local_version)


def check_and_maybe_install(
    emit: Callable[[str], None] = default_emit,
    *,
    auto_install: bool = False,
    confirm_install: Callable[[str], bool] | None = None,
) -> dict[str, Any]:
    """
    Shared implementation behind BOTH the "Check Updates" button and the
    automatic check that runs on application startup. See module
    docstring for the full behavior matrix of auto_install/confirm_install.
    """
    local_version = read_local_version(emit)
    try:
        entry = fetch_registry_entry()
        remote_version = canonical_version(entry.version)
        if not is_remote_newer(remote_version, local_version):
            if normalize_version(remote_version) == normalize_version(local_version):
                status, message = "current", "The installed version matches the registry version."
            else:
                status, message = "local_newer", "The local version is newer than the registry version."
            return build_update_result(status=status, local_version=local_version, remote_version=remote_version, message=message)

        should_install = auto_install
        if not should_install and confirm_install is not None:
            emit("Prompting the user before downloading the available update...")
            should_install = bool(confirm_install(remote_version))
            if not should_install:
                return build_update_result(
                    status="declined", local_version=local_version, remote_version=remote_version,
                    changelog=entry.changelog,
                    message=(
                        "The user chose not to download or install this update right now. "
                        "It will be offered again the next time the app checks for updates."
                    ),
                )

        verified_path = download_and_verify_release(entry, emit)

        if not should_install:
            return build_update_result(
                status="downloaded", local_version=local_version, remote_version=remote_version,
                downloaded_file=verified_path, changelog=entry.changelog,
                message="A newer, signature-verified update package was downloaded but not installed.",
            )

        return _apply_verified_release(entry, verified_path, local_version, remote_version, emit)
    except Exception as exc:
        return _map_exception(exc, local_version)
