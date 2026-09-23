"""
services/tooling_manager.py
Core logic behind the Tooling page: downloading, verifying, installing,
running, and update-checking every program listed in
config/tooling_catalog.py. This is the Tooling equivalent of
services/updater/orchestration.py, reusing the SAME registry-fetch and
signed-download-and-verify machinery already built for the Archive's
own self-updater -- every program installed through this page goes
through the identical hash-then-signature verification gate as an
Archive self-update, via the shared registry page on
brisartresearcharchive.com (one JSON object, one key per app_id).

Talks to:
  - config/tooling_catalog.py: static list of installable programs and
    their registry app_ids / expected executable paths.
  - config/tooling_state.py: persisted record of what's installed,
    which version, and where -- this module is the only writer to it.
  - services/updater/registry.py: fetch_registry_entry(app_id=...) is
    reused UNCHANGED to look up each program's current published
    version, exactly as it's used for the Archive's own updates, just
    with a different app_id per call.
  - services/updater/download.py: download_and_verify_release(entry,
    emit) is reused UNCHANGED -- every Tooling download goes through
    the identical hash-match-then-signature-verify gate as an Archive
    self-update. A program whose signature fails to verify is REJECTED
    here exactly as it would be for the Archive itself; nothing from
    an unverified download is ever installed.
  - services/updater/versioning.py: is_remote_newer()/canonical_version()
    reused for the "is there an update" comparison shown on the
    Tooling page and in the startup update-check popup.
  - gui/pages/tooling_page.py calls download_and_install_tool(),
    run_tool(), open_tool_install_folder() directly (via
    controllers/system_controller.py wrappers, same layering as every
    other page's actions).
  - gui/main_window.py calls check_all_tool_updates() once at startup
    (chained after the Archive's own self-update check), and
    gui/pages/tooling_page.py's "Check for Tool Updates" button calls
    it on demand.

SAFE ZIP EXTRACTION, specifically:
A downloaded, hash-and-signature-verified zip could still (in
principle, e.g. from a bug in the signing/build pipeline rather than a
malicious source, since it already passed signature verification by
this point) contain a path-traversal entry (e.g. "../../evil.exe") or
be a "zip bomb" (a tiny file that decompresses to an enormous size).
_safe_extract_zip() guards against both:
  - every member's resolved destination path is checked to still be
    inside the target install directory before being written; any
    entry that would escape it is rejected and the WHOLE extraction is
    aborted (nothing partial is left behind) rather than silently
    skipping just that one entry.
  - the sum of all members' uncompressed sizes is checked against
    MAX_UNCOMPRESSED_EXTRACT_BYTES before any file is written; an
    oversized archive is rejected the same way.
This mirrors the same category of defense already used for the
Archive's own self-update path -- kept as a self-contained
implementation in this module (rather than assuming a shared helper
elsewhere) so this module has no unverified dependency on another
subsystem's internal function signatures.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys as platform_sys
import zipfile
from pathlib import Path
from typing import Any, Callable

from config.tooling_catalog import get_catalog_entry
from config.tooling_state import get_install_dir, get_tool_record, is_tool_installed, record_tool_installed
from services.updater.download import download_and_verify_release
from services.updater.registry import RegistryError, VerificationError, fetch_registry_entry
from services.updater.versioning import canonical_version, is_remote_newer, normalize_version

# Any single Tooling download that would decompress to more than this
# many bytes is rejected outright rather than extracted -- see the
# module docstring's SAFE ZIP EXTRACTION section.
MAX_UNCOMPRESSED_EXTRACT_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB


def build_result(*, status: str, tool_id: str, message: str = "", version: str = "", changelog: str = "") -> dict[str, Any]:
    return {
        "status": str(status),
        "tool_id": str(tool_id),
        "message": str(message),
        "version": str(version),
        "changelog": str(changelog),
    }


def _safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    """
    Extracts `zip_path` into `dest_dir`, raising ValueError if the
    archive contains a path-traversal entry or exceeds
    MAX_UNCOMPRESSED_EXTRACT_BYTES -- see the module docstring for why.
    Extraction is all-or-nothing: dest_dir is only ever populated after
    every member has already passed both checks.
    """
    dest_dir = dest_dir.resolve()
    with zipfile.ZipFile(zip_path, "r") as archive:
        members = archive.infolist()
        total_uncompressed = sum(member.file_size for member in members)
        if total_uncompressed > MAX_UNCOMPRESSED_EXTRACT_BYTES:
            raise ValueError(
                f"Archive would decompress to {total_uncompressed} bytes, "
                f"exceeding the {MAX_UNCOMPRESSED_EXTRACT_BYTES}-byte limit. Rejected."
            )
        resolved_targets: list[tuple[zipfile.ZipInfo, Path]] = []
        for member in members:
            member_path = (dest_dir / member.filename).resolve()
            if member_path != dest_dir and dest_dir not in member_path.parents:
                raise ValueError(
                    f"Archive member {member.filename!r} would extract outside "
                    f"the install directory. Rejected as a path-traversal attempt."
                )
            resolved_targets.append((member, member_path))
        dest_dir.mkdir(parents=True, exist_ok=True)
        for member, target_path in resolved_targets:
            if member.is_dir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member, "r") as source, open(target_path, "wb") as destination:
                shutil.copyfileobj(source, destination)


def download_and_install_tool(tool_id: str, emit: Callable[[str], None]) -> dict[str, Any]:
    """
    Downloads, verifies, and installs (or updates) one program from the
    Tooling catalog. Used for both a fresh install (nothing previously
    recorded for this tool_id) and an update (a newer version was found
    by check_all_tool_updates()) -- the logic is identical either way:
    fetch the current registry entry, download+verify it exactly as an
    Archive self-update would, then replace whatever was previously in
    this tool's install folder with the freshly verified contents.

    Returns a result dict with "status" one of:
      "installed"       -- succeeded, tool is now installed/updated.
      "unknown_tool"    -- tool_id isn't in config.tooling_catalog at all.
      "registry_error"  -- couldn't find/reach this program's registry entry.
      "verification_failed" -- hash or signature check failed; nothing installed.
      "asset_error"     -- the registry entry's asset_kind isn't "zip" or
                           "exe", or the downloaded file couldn't be
                           extracted/copied into place.
      "unexpected_error" -- any other failure, message includes detail.
    """
    catalog_entry = get_catalog_entry(tool_id)
    if catalog_entry is None:
        return build_result(status="unknown_tool", tool_id=tool_id, message=f"{tool_id!r} is not a known Tooling program.")

    try:
        registry_entry = fetch_registry_entry(app_id=tool_id)
    except RegistryError as exc:
        return build_result(status="registry_error", tool_id=tool_id, message=str(exc))

    try:
        verified_path = download_and_verify_release(registry_entry, emit)
    except VerificationError as exc:
        return build_result(status="verification_failed", tool_id=tool_id, message=str(exc))
    except Exception as exc:
        return build_result(status="unexpected_error", tool_id=tool_id, message=f"{type(exc).__name__}: {exc}")

    install_dir = get_install_dir(tool_id)
    try:
        if registry_entry.asset_kind == "zip":
            if install_dir.exists():
                shutil.rmtree(install_dir)
            _safe_extract_zip(Path(verified_path), install_dir)
        elif registry_entry.asset_kind == "exe":
            install_dir.mkdir(parents=True, exist_ok=True)
            destination = install_dir / catalog_entry["executable"]
            shutil.copy2(verified_path, destination)
        else:
            return build_result(
                status="asset_error", tool_id=tool_id,
                message=f"Unrecognized asset_kind {registry_entry.asset_kind!r} for {tool_id!r}.",
            )
    except (OSError, ValueError, zipfile.BadZipFile, zipfile.LargeZipFile) as exc:
        return build_result(status="asset_error", tool_id=tool_id, message=f"{type(exc).__name__}: {exc}")

    remote_version = canonical_version(registry_entry.version)
    record_tool_installed(tool_id, remote_version, str(install_dir))
    emit(f"{catalog_entry['name']} installed: version {remote_version} at {install_dir}")
    return build_result(
        status="installed", tool_id=tool_id, version=remote_version,
        changelog=registry_entry.changelog,
        message=f"{catalog_entry['name']} installed successfully (version {remote_version}).",
    )


def run_tool(tool_id: str) -> dict[str, Any]:
    """
    Launches an installed program's executable (config.tooling_catalog's
    "executable" field, resolved relative to this tool's install
    directory). Returns "not_installed" if there's no install record,
    "missing_executable" if the record exists but the expected file is
    gone (e.g. manually deleted), or "launched"/"launch_failed"
    otherwise. Never blocks -- subprocess.Popen starts the program and
    returns immediately, exactly like SystemController.start_framework().
    """
    catalog_entry = get_catalog_entry(tool_id)
    if catalog_entry is None:
        return build_result(status="unknown_tool", tool_id=tool_id, message=f"{tool_id!r} is not a known Tooling program.")

    record = get_tool_record(tool_id)
    if record is None:
        return build_result(status="not_installed", tool_id=tool_id, message=f"{catalog_entry['name']} is not installed yet.")

    executable_path = Path(record["install_path"]) / catalog_entry["executable"]
    if not executable_path.exists():
        return build_result(
            status="missing_executable", tool_id=tool_id,
            message=f"Expected {executable_path}, but it was not found. The install may have been moved or deleted.",
        )
    try:
        subprocess.Popen([str(executable_path)], cwd=str(executable_path.parent))
    except OSError as exc:
        return build_result(status="launch_failed", tool_id=tool_id, message=f"{type(exc).__name__}: {exc}")
    return build_result(status="launched", tool_id=tool_id, message=f"Launched {catalog_entry['name']}.")


def open_tool_install_folder(tool_id: str) -> dict[str, Any]:
    """Opens an installed program's install folder in the OS file
    explorer -- same cross-platform approach as
    SystemController.open_output_folder()."""
    catalog_entry = get_catalog_entry(tool_id)
    if catalog_entry is None:
        return build_result(status="unknown_tool", tool_id=tool_id, message=f"{tool_id!r} is not a known Tooling program.")

    record = get_tool_record(tool_id)
    if record is None:
        return build_result(status="not_installed", tool_id=tool_id, message=f"{catalog_entry['name']} is not installed yet.")

    folder_path = Path(record["install_path"])
    if not folder_path.exists():
        return build_result(status="missing_folder", tool_id=tool_id, message=f"{folder_path} no longer exists.")
    try:
        if platform_sys.platform.startswith("win"):
            os.startfile(str(folder_path))  # noqa: S606
        elif platform_sys.platform == "darwin":
            subprocess.run(["open", str(folder_path)], check=False)
        else:
            subprocess.run(["xdg-open", str(folder_path)], check=False)
    except Exception as exc:
        return build_result(status="open_failed", tool_id=tool_id, message=f"{type(exc).__name__}: {exc}")
    return build_result(status="opened", tool_id=tool_id, message=f"Opened folder: {folder_path}")


def check_all_tool_updates(emit: Callable[[str], None]) -> list[dict[str, Any]]:
    """
    Checks every CURRENTLY INSTALLED Tooling program (not the whole
    catalog -- a program that was never downloaded has no installed
    version to compare against, so it's skipped) against its registry
    entry, and returns a list of result dicts for every one that has a
    newer version published than what's installed. Programs that are
    already current, or whose registry check fails, are simply omitted
    from the returned list (a failed check for one program's registry
    entry never stops the others from being checked) -- callers that
    want failure detail should inspect the emitted log lines, not this
    return value, since this is specifically "what needs updating."
    """
    upgrade_candidates: list[dict[str, Any]] = []
    for catalog_entry in _installed_catalog_entries():
        tool_id = catalog_entry["id"]
        record = get_tool_record(tool_id)
        if record is None:
            continue
        try:
            registry_entry = fetch_registry_entry(app_id=tool_id)
        except RegistryError as exc:
            emit(f"{catalog_entry['name']}: could not check for updates ({exc})")
            continue
        remote_version = canonical_version(registry_entry.version)
        local_version = normalize_version(record["installed_version"])
        if is_remote_newer(remote_version, local_version):
            upgrade_candidates.append({
                "tool_id": tool_id,
                "name": catalog_entry["name"],
                "installed_version": record["installed_version"],
                "available_version": remote_version,
                "changelog": registry_entry.changelog,
            })
    return upgrade_candidates


def _installed_catalog_entries() -> list[dict]:
    from config.tooling_catalog import TOOLING_CATALOG
    return [entry for entry in TOOLING_CATALOG if is_tool_installed(entry["id"])]


__all__ = [
    "MAX_UNCOMPRESSED_EXTRACT_BYTES", "download_and_install_tool", "run_tool",
    "open_tool_install_folder", "check_all_tool_updates",
]
