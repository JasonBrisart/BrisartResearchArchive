"""Purpose
-------
Verify CPU sizing, real spawned work, ordered recovery, cancellation boundaries, and progress on skipped and failed files.

This regression test module defines `TestParallelImport`. Its scope is deliberately limited to
the responsibilities visible in this file rather than duplicating the application-wide
workflow. Its fixtures and assertions describe observable behavior without changing the
installed application.

Communication / relationships
-----------------------------
Uses the ingestion scheduler with a picklable local probe, plus an index spy.

The direct in-project imports visible in this module are `brisart_ai.knowledge`. Test methods
`test_available_cores_and_windows_capacity`, `test_one_file_or_one_core_does_not_create_pool`,
`test_spawned_workers_prepare_files_but_caller_writes_in_order`,
`test_progress_counts_skips_and_write_failures_but_not_as_indexed`,
`test_pool_failure_retries_only_the_pending_suffix`; this identifies where behavior is invoked
without implying a separate hidden dependency. The test runner supplies the test lifecycle and
any temporary fixtures.

Settings / parameters
---------------------
Two real child processes rendezvous in a temporary directory.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
One file stays in process, and lost workers must not replay completed work.

The behaviors documented above must be read together with the actual branches in
test_parallel_import.py; assertions should reject regressions rather than merely checking file
layout. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
The worker probe tests multiprocessing plumbing, not official native readers.
The existing test_ingest.py suite exercises those readers with a real index.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python -m pytest brisart_ai/knowledge/tests/test_parallel_import.py -q

For a concrete entry point, inspect `TestParallelImport`; run this module through the existing
project test runner with its actual test path. The example above is illustrative of this
file's present interface; do not treat it as an instruction to create additional state or call
private functions directly.
"""

from concurrent.futures import Future
from concurrent.futures.process import BrokenProcessPool
import os
from pathlib import Path
import tempfile
from threading import Event
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from brisart_ai.knowledge import ingest


def _worker_probe(path):
    pid = os.getpid()
    (path.parent / f"pid-{pid}").touch()
    deadline = time.monotonic() + 15
    while len(list(path.parent.glob("pid-*"))) < 2:
        if time.monotonic() >= deadline:
            raise AssertionError("Two import workers did not run concurrently")
        time.sleep(0.01)
    return ingest._PreparedFile(path.read_text(encoding="utf-8"), digest=str(pid))


class TestParallelImport(unittest.TestCase):
    def test_available_cores_and_windows_capacity(self):
        for name, reported, expected in (("posix", 96, 96), ("nt", 96, 61), ("nt", 8, 8)):
            with self.subTest(platform=name, reported=reported):
                system = SimpleNamespace(name=name, process_cpu_count=lambda: reported)
                with patch.object(ingest, "os", system):
                    self.assertEqual(ingest._available_workers(), expected)
        for affinity, count, expected in (({0, 3, 5}, 64, 3), (set(), None, 1)):
            system = SimpleNamespace(name="posix", sched_getaffinity=lambda _: affinity,
                                     cpu_count=lambda: count)
            with patch.object(ingest, "os", system):
                self.assertEqual(ingest._available_workers(), expected)

    def test_one_file_or_one_core_does_not_create_pool(self):
        for cores, names in ((8, ["one"]), (1, ["one", "two"]), (8, [])):
            with self.subTest(cores=cores, names=names):
                paths = list(map(Path, names))
                with patch.object(ingest, "_available_workers", return_value=cores), \
                        patch.object(ingest, "ProcessPoolExecutor") as pool, \
                        patch.object(ingest, "_prepare_file", return_value=ingest._PreparedFile("text")):
                    self.assertEqual([path for path, _ in ingest._prepared_files(paths)], paths)
                    pool.assert_not_called()

    def test_spawned_workers_prepare_files_but_caller_writes_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / f"file-{i}.txt" for i in range(8)]
            for path in paths:
                path.write_text(path.stem, encoding="utf-8")
            readers = ModuleType("brisart_ai.io.readers")
            readers.iter_supported_files = lambda _paths: iter(paths)
            writes = []
            updates = []
            index = SimpleNamespace(add_source=lambda **row: writes.append((os.getpid(), row)) or True)
            with patch.object(ingest, "_available_workers", return_value=2), \
                    patch.object(ingest, "_prepare_file", _worker_probe), \
                    patch.dict("sys.modules", {readers.__name__: readers}):
                self.assertEqual(ingest.ingest_paths([directory], index,
                    on_progress=lambda *event: updates.append(event)), len(paths))
            self.assertEqual(updates, [(i, len(paths), i) for i in range(len(paths) + 1)])
            self.assertEqual([row["text"] for _, row in writes], [path.stem for path in paths])
            self.assertEqual({pid for pid, _ in writes}, {os.getpid()})
            child_pids = {int(row["content_hash"]) for _, row in writes}
            self.assertEqual(len(child_pids), 2)
            self.assertNotIn(os.getpid(), child_pids)

    def test_progress_counts_skips_and_write_failures_but_not_as_indexed(self):
        paths = list(map(Path, ["good.txt", "empty.txt", "error.txt", "write.txt"]))
        readers = ModuleType("brisart_ai.io.readers")
        readers.iter_supported_files = lambda _paths: iter(paths)
        prepared = [ingest._PreparedFile("good"), ingest._PreparedFile(""),
                    ingest._PreparedFile("", error="cannot read"), ingest._PreparedFile("write")]
        updates = []

        def write(**row):
            if row["title"] == "write.txt":
                raise OSError("cannot write")
            return True

        with patch.object(ingest, "_prepared_files", side_effect=lambda found: zip(found, prepared)), \
                patch.dict("sys.modules", {readers.__name__: readers}):
            self.assertEqual(ingest.ingest_paths(["root"], SimpleNamespace(add_source=write),
                on_progress=lambda *event: updates.append(event)), 1)
        self.assertEqual(updates, [(0, 4, 0), (1, 4, 1), (2, 4, 1), (3, 4, 1), (4, 4, 1)])

    def test_pool_failure_retries_only_the_pending_suffix(self):
        paths = list(map(Path, "abcdef"))
        first, broken = Future(), Future()
        first.set_result(ingest._PreparedFile("parallel"))
        broken.set_exception(BrokenProcessPool("worker stopped"))
        with patch.object(ingest, "_available_workers", return_value=2), \
                patch.object(ingest, "ProcessPoolExecutor") as executor, \
                patch.object(ingest, "_prepare_file", return_value=ingest._PreparedFile("serial")) as serial:
            pool = executor.return_value
            pool.submit.side_effect = [first, broken, Future(), Future(), Future()]
            results = list(ingest._prepared_files(paths))
        self.assertEqual([path for path, _ in results], paths)
        self.assertEqual([prepared.text for _, prepared in results], ["parallel"] + ["serial"] * 5)
        self.assertEqual([call.args[0] for call in serial.call_args_list], paths[1:])

    def test_cancel_during_selected_parallel_file_indexes_only_that_file(self):
        paths = list(map(Path, ["a.txt", "b.txt", "c.txt", "d.txt", "e.txt"]))
        stop = Event()
        readers = ModuleType("brisart_ai.io.readers")
        readers.iter_supported_files = lambda _paths, **_kwargs: iter(paths)
        writes, updates = [], []
        selected = Future()
        queued = [Future() for _ in range(3)]

        def complete_current(_futures, *, timeout):
            stop.set()
            selected.set_result(ingest._PreparedFile("current"))

        index = SimpleNamespace(add_source=lambda **row: writes.append(row["title"]) or True)
        with patch.object(ingest, "_available_workers", return_value=2), \
                patch.object(ingest, "ProcessPoolExecutor") as executor, \
                patch.object(ingest, "wait", side_effect=complete_current), \
                patch.dict("sys.modules", {readers.__name__: readers}):
            pool = executor.return_value
            pool.submit.side_effect = [selected, *queued]
            self.assertEqual(ingest.ingest_paths(["root"], index, should_stop=stop.is_set,
                on_progress=lambda *event: updates.append(event)), 1)
            self.assertEqual(pool.submit.call_count, 4)
            pool.shutdown.assert_called_once_with(wait=True, cancel_futures=True)
        self.assertEqual(writes, ["a.txt"])
        self.assertEqual(updates, [(0, 5, 0), (1, 5, 1)])

    def test_cancel_during_serial_reader_finishes_current_without_starting_next(self):
        paths = list(map(Path, ["a.txt", "b.txt"]))
        stop = Event()

        def read(_path):
            stop.set()
            return ingest._PreparedFile("current")

        with patch.object(ingest, "_available_workers", return_value=1), \
                patch.object(ingest, "_prepare_file", side_effect=read) as prepare:
            self.assertEqual([path for path, _ in ingest._prepared_files(paths, should_stop=stop.is_set)], paths[:1])
            prepare.assert_called_once_with(paths[0])

    def test_cancel_before_preparation_never_starts_workers(self):
        with patch.object(ingest, "ProcessPoolExecutor") as pool:
            self.assertEqual(list(ingest._prepared_files([Path("a.txt")], should_stop=lambda: True)), [])
            pool.assert_not_called()

    def test_pool_start_failure_does_not_drop_files(self):
        paths = list(map(Path, "abc"))
        with patch.object(ingest, "_available_workers", return_value=2), \
                patch.object(ingest, "ProcessPoolExecutor", side_effect=OSError("worker unavailable")), \
                patch.object(ingest, "_prepare_file", return_value=ingest._PreparedFile("serial")):
            self.assertEqual([path for path, _ in ingest._prepared_files(paths)], paths)
