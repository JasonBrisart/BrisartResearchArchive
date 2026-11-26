"""Purpose
-------
Import local files with automatic multicore extraction and hashing.

Communication / relationships
-----------------------------
Readers discover unique supported paths. Spawned workers prepare text and file
metadata; only the caller writes to the index, in discovery order.

Settings / parameters
---------------------
Worker count is automatic: available logical CPUs, bounded by the work and the
Windows executor limit. At most two tasks per worker are queued at a time.
An optional callback reports (processed, total, indexed) after discovery and after each file.

Edge cases
----------
Empty and one-file imports need no pool. Unavailable workers trigger serial
processing for the uncommitted remainder. Cancellation stops discovery or stops after
the selected file; dispatched preparations drain without writing to SQLite. File
errors do not stop the import.

Known limitations
-----------------
Progress callers retain discovered paths to know the total before indexing.
SQLite writes and posting construction remain serial. Small batches can cost
more to start than they save. Files modified during import are not locked.

Examples
--------
ingest_paths(["notes.md", "reference/"], index)
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from itertools import chain, islice
from multiprocessing import get_context
import os
from pathlib import Path
from typing import Callable, Iterable, NamedTuple


class _PreparedFile(NamedTuple):
    text: str
    size: int = 0
    digest: str = ""
    error: str = ""
    warning: str = ""


def _prepare_file(path: Path) -> _PreparedFile:
    from brisart_ai.io.readers import read_file
    from brisart_ai.util import file_hash

    try:
        text = read_file(path)
        if not text or not text.strip():
            return _PreparedFile("")
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        try:
            return _PreparedFile(text, size, file_hash(path))
        except OSError as exc:
            return _PreparedFile(text, size, warning=f"could not hash {path}: {exc}")
    except Exception as exc:
        return _PreparedFile("", error=f"could not ingest {path}: {exc}")


def _available_workers() -> int:
    process_cpu_count = getattr(os, "process_cpu_count", None)
    count = process_cpu_count() if process_cpu_count else None
    if count is None and hasattr(os, "sched_getaffinity"):
        try:
            count = len(os.sched_getaffinity(0))
        except OSError:
            pass
    count = count or os.cpu_count() or 1
    return min(count, 61) if os.name == "nt" else count


def _prepared_files(paths: Iterable[Path], *, should_stop: Callable[[], bool] | None = None):
    stopped = should_stop or (lambda: False)
    if stopped():
        return
    remaining = iter(paths)
    capacity = _available_workers()
    initial = list(islice(remaining, 2 * capacity))
    if capacity == 1 or len(initial) < 2:
        for path in chain(initial, remaining):
            if stopped():
                return
            yield path, _prepare_file(path)
        return

    # Keep path order and track the uncommitted suffix even if submission fails.
    workers = min(capacity, len(initial))
    backlog = deque(initial)
    in_flight = deque()
    try:
        pool = ProcessPoolExecutor(max_workers=workers, mp_context=get_context("spawn"))
        try:
            while (backlog or in_flight) and not stopped():
                while len(in_flight) < 2 * workers and backlog and not stopped():
                    path = backlog[0]
                    in_flight.append((path, pool.submit(_prepare_file, path)))
                    backlog.popleft()
                if stopped():
                    break
                # This is the one file allowed to reach SQLite if shutdown is requested.
                path, future = in_flight[0]
                if should_stop is not None:
                    while not future.done():
                        if stopped():
                            for _, later in islice(in_flight, 1, None):
                                later.cancel()
                            break
                        wait((future,), timeout=0.1)
                prepared = future.result()
                in_flight.popleft()
                yield path, prepared
                if stopped():
                    break
                path = next(remaining, None)
                if path is not None:
                    backlog.append(path)
        finally:
            # Discard futures that have not started; dispatched work drains without indexing.
            pool.shutdown(wait=True, cancel_futures=True)
    except (BrokenProcessPool, OSError) as exc:
        if stopped():
            return
        print(f"WARN: parallel import unavailable; continuing serially: {exc}")
        for path in chain((path for path, _ in in_flight), backlog, remaining):
            if stopped():
                return
            yield path, _prepare_file(path)


def ingest_paths(paths: Iterable[str], index, *, on_progress: Callable[[int, int, int], None] | None = None,
                 should_stop: Callable[[], bool] | None = None) -> int:
    """Ingest supported files from paths into the supplied index."""
    from brisart_ai.io.readers import iter_supported_files

    discovered = (iter_supported_files(paths, should_stop=should_stop) if should_stop is not None
                  else iter_supported_files(paths))
    files = list(discovered) if on_progress is not None else discovered
    total = len(files) if isinstance(files, list) else 0
    if on_progress is not None:
        on_progress(0, total, 0)

    count = 0
    prepared_files = (_prepared_files(files, should_stop=should_stop) if should_stop is not None
                      else _prepared_files(files))
    for processed, (path, prepared) in enumerate(prepared_files, 1):
        try:
            if prepared.error:
                print(f"WARN: {prepared.error}")
                continue
            if prepared.warning:
                print(f"WARN: {prepared.warning}")
            if not prepared.text:
                print(f"SKIPPED EMPTY: {path}")
                continue
            try:
                indexed = index.add_source(
                    source_type="file", location=str(path), title=path.name, text=prepared.text,
                    content_hash=prepared.digest, size_bytes=prepared.size,
                    extension=path.suffix.lower(),
                )
            except Exception as exc:
                print(f"WARN: could not index {path}: {exc}")
                continue
            count += int(bool(indexed))
            print(f"{'INGESTED' if indexed else 'SKIPPED EMPTY'}: {path}")
        finally:
            if on_progress is not None:
                on_progress(processed, total, count)
    return count


__all__ = ["ingest_paths"]
