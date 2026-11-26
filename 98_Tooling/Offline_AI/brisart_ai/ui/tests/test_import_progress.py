"""Purpose
-------
Verify elapsed labels and honest file-count progress at every import phase.

This regression test module defines `test_discovery_has_elapsed_but_no_percent`,
`test_empty_and_complete_do_not_show_eta`, `test_eta_ignores_discovery_and_waits_for_samples`,
`test_elapsed_time_uses_hours_when_needed`,
`test_stopping_suppresses_live_progress_even_if_more_results_arrive`. Its scope is
deliberately limited to the responsibilities visible in this file rather than duplicating the
application-wide workflow. Its fixtures and assertions describe observable behavior without
changing the installed application.

Communication / relationships
-----------------------------
Uses the same display formatting as Add Sources, without initializing Tk.

The direct in-project imports visible in this module are `brisart_ai.ui.import_progress`. Test
methods `test_discovery_has_elapsed_but_no_percent`,
`test_empty_and_complete_do_not_show_eta`, `test_eta_ignores_discovery_and_waits_for_samples`,
`test_elapsed_time_uses_hours_when_needed`,
`test_stopping_suppresses_live_progress_even_if_more_results_arrive`; this identifies where
behavior is invoked without implying a separate hidden dependency. The test runner supplies
the test lifecycle and any temporary fixtures.

Settings / parameters
---------------------
Fixed monotonic clock readings make estimates deterministic in tests.

Parameters and configuration are supplied at the entry points named above or by the constants
already declared in this file. Test inputs are defined by the test cases and their fixtures,
not production settings. The relevant limits and defaults are those enforced by the executable
code, not assumptions about future integrations.

Edge cases
----------
Discovery, empty folders, initial samples and completed imports omit an ETA.

The behaviors documented above must be read together with the actual branches in
test_import_progress.py; assertions should reject regressions rather than merely checking file
layout. Error handling, input validation, and early returns remain the responsibility of the
concrete functions in this module. No additional fallback is created by this documentation.

Known limitations
-----------------
Does not validate Windows widget rendering.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Passing this test module
does not prove the entire Windows desktop or external Native API integration. No compatibility
adapter or speculative extension point has been added as part of this pass.

Examples
--------
python -m pytest brisart_ai/ui/tests/test_import_progress.py -q

For a concrete entry point, inspect `test_discovery_has_elapsed_but_no_percent`,
`test_empty_and_complete_do_not_show_eta`, `test_eta_ignores_discovery_and_waits_for_samples`,
`test_elapsed_time_uses_hours_when_needed`,
`test_stopping_suppresses_live_progress_even_if_more_results_arrive`; run this module through
the existing project test runner with its actual test path. The example above is illustrative
of this file's present interface; do not treat it as an instruction to create additional state
or call private functions directly.
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
