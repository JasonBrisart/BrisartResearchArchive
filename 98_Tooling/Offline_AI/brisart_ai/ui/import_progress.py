"""Purpose
-------
Format elapsed time and file-count progress for the desktop workspace.

Communication / relationships
-----------------------------
Add Sources provides monotonic timestamps and ingestion counts. No Tk or I/O.

Settings / parameters
---------------------
ETA uses average throughput after at least two completed files and one second.

Edge cases
----------
Discovery has no percentage. Empty or canceling batches show no ETA.

Known limitations
-----------------
Files can differ considerably in size and cost; the ETA can move in either direction.

Examples
--------
progress_text(18.0, 0.0, (6, 10, 5, 6.0))
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
