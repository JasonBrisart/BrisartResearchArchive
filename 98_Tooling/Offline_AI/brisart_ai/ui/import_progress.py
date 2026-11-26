"""Purpose
-------
Format elapsed time and file-count progress for the desktop workspace.

This desktop presentation component defines `elapsed_label`, `progress_text`. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Callers use these declarations through the module interface; the
file is not a separate service or background daemon unless explicitly stated above.

Communication / relationships
-----------------------------
Add Sources provides monotonic timestamps and ingestion counts. No Tk or I/O.

The direct in-project imports visible in this module are the standard library and its direct
caller. Public entry points `elapsed_label`, `progress_text`; this identifies where behavior
is invoked without implying a separate hidden dependency. Higher-level coordination remains
with the calling layer rather than being introduced here.

Settings / parameters
---------------------
ETA uses average throughput after at least two completed files and one second.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. This documentation pass does not introduce a new configuration
key, command option, or persisted value. The relevant limits and defaults are those enforced
by the executable code, not assumptions about future integrations.

Edge cases
----------
Discovery has no percentage. Empty or canceling batches show no ETA.

The behaviors documented above must be read together with the actual branches in
import_progress.py; a caller must not infer success from an empty, rejected, or unsupported
result. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Files can differ considerably in size and cost; the ETA can move in either direction.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
progress_text(18.0, 0.0, (6, 10, 5, 6.0))

For a concrete entry point, inspect `elapsed_label`, `progress_text`; invoke it through the
existing application entry point or its documented caller. The example above is illustrative
of this file's present interface; do not treat it as an instruction to create additional state
or call private functions directly.
"""

from math import ceil


def elapsed_label(seconds: float) -> str:
    minutes, seconds = divmod(max(0, int(seconds)), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"


def progress_text(now: float, started: float, snapshot, *, stopping=False):
    elapsed = elapsed_label(now - started)
    if stopping:
        return None, f"No new files will be imported  |  Elapsed {elapsed}"
    if snapshot is None:
        return None, f"Finding supported files...  |  Elapsed {elapsed}"
    processed, total, indexed, discovered_at = snapshot
    if not total:
        return 0, f"No supported files found  |  Elapsed {elapsed}"
    remaining = total - processed
    percent = 100 * processed // total
    text = (f"{percent}%  |  {processed:,}/{total:,} processed  |  {remaining:,} left"
            f"  |  {indexed:,} indexed  |  Elapsed {elapsed}")
    if not remaining:
        return percent, text
    active_seconds = now - discovered_at
    if processed < 2 or active_seconds < 1:
        return percent, f"{text}  |  Estimating time left..."
    eta = elapsed_label(ceil(active_seconds * remaining / processed))
    return percent, f"{text}  |  About {eta} left"

