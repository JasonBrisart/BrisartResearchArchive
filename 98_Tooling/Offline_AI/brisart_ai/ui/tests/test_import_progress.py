"""Purpose
-------
Verify elapsed labels and honest file-count progress at every import phase.

Communication / relationships
-----------------------------
Uses the same display formatting as Add Sources, without initializing Tk.

Settings / parameters
---------------------
Fixed monotonic clock readings make estimates deterministic in tests.

Edge cases
----------
Discovery, empty folders, initial samples and completed imports omit an ETA.

Known limitations
-----------------
Does not validate Windows widget rendering.

Examples
--------
python -m pytest brisart_ai/ui/tests/test_import_progress.py -q
"""

from brisart_ai.ui.import_progress import elapsed_label, progress_text


def test_discovery_has_elapsed_but_no_percent():
    percent, text = progress_text(75, 12, None)
    assert percent is None
    assert "Finding supported files" in text and "Elapsed 1:03" in text


def test_empty_and_complete_do_not_show_eta():
    assert progress_text(10, 0, (0, 0, 0, 3)) == (0, "No supported files found  |  Elapsed 0:10")
    percent, text = progress_text(10, 0, (4, 4, 3, 3))
    assert percent == 100
    assert "0 left" in text and "3 indexed" in text and "About" not in text


def test_eta_ignores_discovery_and_waits_for_samples():
    assert "Estimating" in progress_text(12, 0, (1, 5, 1, 9))[1]
    percent, text = progress_text(18, 0, (6, 10, 5, 6))
    assert percent == 60 and "4 left" in text and "About 0:08 left" in text


def test_elapsed_time_uses_hours_when_needed():
    assert elapsed_label(3661.9) == "1:01:01"


def test_stopping_suppresses_live_progress_even_if_more_results_arrive():
    expected = (None, "No new files will be imported  |  Elapsed 0:18")
    for snapshot in (None, (0, 0, 0, 6), (6, 10, 5, 6), (7, 10, 6, 6)):
        assert progress_text(18, 0, snapshot, stopping=True) == expected


def test_retry_returns_to_live_progress():
    snapshot = (6, 10, 5, 6)
    assert progress_text(18, 0, snapshot, stopping=True)[0] is None
    assert progress_text(18, 0, snapshot)[0] == 60
