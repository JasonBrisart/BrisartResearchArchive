# Changelog

All notable changes to Brisart Research Archive are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.4.9 ALPHA] - 2026-08-16

### Added
- TFL now shows a pre-session Run Options screen before starting a session, exposing Extra Stimuli, Perturbations, Probes, and Delayed Reentry as toggles.
- Added Restore Defaults, Cancel, and Start Session controls to the new TFL options screen.
- Added an optional participant ID prompt when launching TFL from the GUI.

### Fixed
- Fixed TFL launching directly into a session and skipping the options screen entirely. `session_gui.py` previously built the engine and rendered the trial screen immediately, so `options_screen.py` was never actually called.
- Fixed the TFL options/session window potentially opening behind the main application window by forcing it to the front on open.
- Fixed silent failures when the options screen could not render. Errors are now logged and shown in a visible dialog instead of leaving a blank or invisible window.
- Fixed trial/stimuli generation now happening only after the user confirms options, instead of before the options screen is shown.

### Changed
- Reordered TFL session startup: options screen first, engine/stimuli/trials built only after "Start Session" is clicked.
- Config values chosen on the options screen are now applied directly before session build, so toggling a setting reliably changes that run's behavior.

### Notes
- No changes were required to `options_screen.py`, `screen.py`, `engine.py`, `config.py`, `stimuli.py`, or `trial_builder.py` - the fix was isolated entirely to `session_gui.py`'s startup flow.
- This closes the gap between the console AIO launcher's options menu and the GUI's TFL launch flow.

---

## [0.4.8 ALPHA] - 2026-08-16

### Changed
- Simplified the Dashboard into a minimal landing page with quick access cards for Frameworks, Results, Archive, and System.
- Removed the previous dashboard status blocks that duplicated information already available in the System page.
- Replaced the experimental workspace/output dashboard concepts with a cleaner placeholder dashboard so future dashboard features can be redesigned without clutter.
- Updated Dashboard quick actions to focus on basic navigation and currently selected framework execution.
- Removed the visible version label from the left sidebar menu to reduce visual noise and keep version details within the appropriate system-level areas.

### Fixed
- Replaced the broken Dashboard page implementation that caused a syntax error during application startup.
- Replaced the broken Sidebar implementation that caused an unterminated string literal error during application startup.
- Restored clean application launch behavior after simplifying the Dashboard and Sidebar files.

### Notes
- The Dashboard is now intentionally minimal.
- The sidebar remains the primary navigation surface.
- Future dashboard cards can be added later without changing the page registry, framework system, or application shell.

---

## [0.4.7] - 2026-08-16

### Removed
- **8 non-functional cards removed across three pages** to cut UI clutter that had no real purpose (no click action, unbuilt placeholders, or duplicated content):
  - **Archive page**: removed "Lab Workflow" (duplicated Dashboard's Recommended Workflow), "Architecture Notes", "Framework Runner Rule", "Shared Layer Rule" (pure prose, no action), and "Future Archive Areas" (placeholder wishlist for 8 unbuilt features). Archive page now contains only the functional "Open Archive Document" card.
  - **Dashboard page**: removed "Engine/Shell Split" and "Local-First Rule" (pure architecture philosophy text, no action).
  - **System page**: removed "Brisart Standards" (placeholder listing four standards docs that don't exist yet).
- Frameworks and Results pages were left unchanged — every card there already triggers a real action.

---

## [0.4.6] - 2026-08-16

### Added
- **Open Folder button** on the System page, next to Browse. Opens the
  currently configured output directory directly in the OS file explorer
  (`os.startfile` on Windows, `open` on macOS, `xdg-open` on Linux).
  - Falls back to the default output folder if the configured path is blank
    or unreadable.
  - Creates the folder first if it doesn't exist yet, so this never silently
    fails on a fresh install.
  - New `SystemController.open_output_folder()` in `controllers/system_controller.py`.
  - Button placed in `gui/pages/system_page.py`, directly under Browse.

---

## [0.4.5] - 2026-08-16

Baseline version for this changelog. Confirmed working state of the
Archive architecture, with the full headless engine / GUI split,
autosave, identity/timestamp fields, and hardened updater already in place.

No changes tracked prior to this version.
