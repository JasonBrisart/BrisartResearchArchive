"""
services/updater/download.py

Downloads a release archive and verifies it -- this is the trust gate
that everything in install.py and exe_swap.py depends on. Verification
requires BOTH a matching SHA256 hash AND a valid RSA signature checked
against the public key embedded in services/trust_anchor.py (never a
key fetched from the registry page). A fully compromised website can
forge a matching hash trivially, but cannot forge a valid signature
without the offline private key.
"""

from __future__ import annotations

import os
import tempfile
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from services import rsa_signing
from services.trust_anchor import get_public_key
from services.updater.archive_safety import sha256_of_file, validate_zip_archive
from services.updater.constants import (
    DOWNLOAD_CHUNK_BYTES,
    DOWNLOAD_TIMEOUT_SECONDS,
    MAX_DOWNLOAD_BYTES,
    UPDATES_DIR,
)
from services.updater.http_utils import build_request, response_final_url
from services.updater.registry import RegistryEntry, VerificationError
from services.updater.versioning import canonical_version, default_emit


def ensure_updates_directory() -> Path:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    return UPDATES_DIR


def remove_file_safely(path: Path) -> None:
    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def response_is_zip(response: Any) -> bool:
    content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()
    allowed_types = {"", "application/zip", "application/x-zip-compressed", "application/octet-stream"}
    return content_type in allowed_types


def download_and_verify_release(entry: RegistryEntry, emit: Callable[[str], None] = default_emit) -> Path:
    """
    Downloads the release archive named in `entry` into UPDATES_DIR, and
    verifies BOTH:
      1. its SHA256 matches entry.sha256, and
      2. that hash carries a valid signature against the public key
         embedded in services/trust_anchor.py -- never a key fetched
         from the registry page itself.

    Raises VerificationError if either check fails. A failed download is
    removed and never handed back to the caller -- nothing downstream
    ever runs on unverified data.
    """
    version = canonical_version(entry.version)
    ensure_updates_directory()
    suffix = ".exe" if entry.asset_kind == "exe" else ".zip"
    output_file = UPDATES_DIR / f"BrisartResearchArchive_{version}{suffix}"

    if output_file.exists() and sha256_of_file(output_file).lower() == entry.sha256.lower():
        emit("Update already downloaded and verified:")
        emit(str(output_file))
        return output_file
    if output_file.exists():
        remove_file_safely(output_file)

    request = build_request(
        entry.download_url,
        "application/zip,application/octet-stream" if entry.asset_kind != "exe" else "application/octet-stream",
    )
    emit("Downloading release...")
    emit(f"Source: {entry.download_url}")
    emit(f"Destination: {output_file}")

    temporary_path: Path | None = None
    total_bytes = 0
    try:
        temporary_descriptor, temporary_name = tempfile.mkstemp(
            prefix=output_file.stem + "_", suffix=suffix + ".part", dir=UPDATES_DIR
        )
        os.close(temporary_descriptor)
        temporary_path = Path(temporary_name)

        with urllib.request.urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            response_final_url(response)
            if entry.asset_kind != "exe" and not response_is_zip(response):
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

        if entry.asset_kind != "exe":
            validate_zip_archive(temporary_path)  # structural safety first

        actual_sha256 = sha256_of_file(temporary_path)
        if actual_sha256.lower() != entry.sha256.lower():
            raise VerificationError(
                f"Hash mismatch. Expected {entry.sha256}, got {actual_sha256}. "
                f"Rejected -- corrupted or tampered download."
            )
        try:
            signature_bytes = bytes.fromhex(entry.signature)
        except ValueError:
            raise VerificationError("Signature in registry entry is not valid hex. Rejected.")
        public_key = get_public_key()
        if not rsa_signing.verify(bytes.fromhex(actual_sha256), signature_bytes, public_key):
            raise VerificationError(
                "SIGNATURE VERIFICATION FAILED. This release does not carry a valid "
                "signature from the embedded trust anchor -- the website may be "
                "compromised, or this release is forged. REJECTED. Nothing was installed."
            )

        temporary_path.replace(output_file)
        temporary_path = None
    except Exception:
        if temporary_path is not None:
            remove_file_safely(temporary_path)
        raise

    emit("Download verified: hash matched, signature valid.")
    emit(f"Bytes downloaded: {total_bytes}")
    emit(f"Saved to: {output_file}")
    return output_file
