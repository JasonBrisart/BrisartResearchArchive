# Changelog
All notable changes to Brisart Research Archive are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.9.0 ALPHA] - 2026-08-27

### Added
- **Tooling page**, a brand new page for downloading, running, and updating separate Brisart-family programs directly from the Archive:
  - `config/tooling_catalog.py` (new): static catalog of installable programs (BrisartIdentityTools, BrisartAI, BrisartOS, Project Context Helper, Entitle, AutoExeBuilder).
  - `config/tooling_state.py` (new): persisted on-disk record of what's installed, which version, and where.
  - `services/tooling_manager.py` (new): download, verify, install, run, and update-check logic — reuses the exact same hash-then-signature verification gate already built for the Archive's own self-updater, so an installed program is verified exactly as rigorously as an Archive update.
  - `services/tool_update_notify.py` (new): popup summary shown when an installed program has a newer version available.
  - `gui/pages/tooling_page.py` (new): one card per program, split into an **Installed** group (top) and an **Available to Download** group (bottom), each sorted alphabetically.
  - New **Tooling** sidebar entry, pinned directly above **Settings** at the bottom of the sidebar, separated by a divider.
  - `controllers/system_controller.py`: new `download_tool()`, `run_tool()`, `open_tool_folder()`, and `check_tool_updates()` methods wiring the page to the manager above.
  - An automatic Tooling update check now runs once at startup, staggered 1 second after the Archive's own self-update check.

### Changed
- **Frameworks page rebuilt** to match the Tooling page's structure and conventions:
  - Removed the "Framework Library" card and its Run Selected Framework / View Results / Refresh Registry actions from this page (all three remain available elsewhere — Dashboard and Results already have them).
  - Replaced the 2-column card grid with a single-column, one-card-per-row layout.
  - Frameworks are now split into an **Available** group (top) and an **Available to Download** group (bottom), each sorted alphabetically by name, instead of one flat list in declared order.
  - Removed the "Select" button; available frameworks now show only **Run** and **Results**.
  - Unavailable frameworks now show **"Not installed."** in the card body (matching Tooling's wording) instead of just the bare description.
  - Replaced "Reserved" / "Coming Soon" badge and button text with **"Available to Download"**, matching Tooling's terminology.
- **Activity Log now shows the newest entry at the top** instead of the bottom, for both new entries logged during the current session and persisted history loaded from previous sessions (`controllers/log_controller.py`, `gui/pages/settings_page.py`).

### Fixed
- **Window now always opens at exactly 800x600 on every launch**, regardless of any window size previously saved to `user_settings.json`. Previously, the 800x600 value was only a *default* — the very first time a user resized the window and closed the app, that saved size was read back and applied on the next launch, silently overriding the intended 800x600 starting size from then on (`gui/main_window.py`).

---

## [0.8.0 ALPHA] - 2026-08-27

### Added
- **Persistent Activity Log** (`config/activity_log.py`, new file): the Activity Log on the Settings page now survives closing and reopening the app. Every action logged via `LogController.log()` is written to a rolling, disk-backed JSON file capped at the most recent **100 entries** (oldest-first, oldest dropped automatically once the cap is reached). Previously the log only ever showed the current session and reset to blank on every relaunch.
- **Yes/No update confirmation dialog**: with "Automatically download and install updates" off and "Notify me about updates" on, the app now asks *"A new update is available. Would you like to download and install it now?"* before touching anything. Declining simply means it asks again next time — nothing is remembered or suppressed.
- **Post-install changelog popup**: when an update installs (manually confirmed or fully automatic), an "Update Installed" popup now shows a summary of what changed, sourced from an optional `changelog` field in the registry entry (`services/updater/registry.py`).
- **Dynamic text wraplength** (`bind_dynamic_wraplength()` in `gui/components/page_helpers.py`): page subtitles and card body text now recalculate their wrap width on every resize instead of using a fixed pixel value, so text reflows correctly at any window size instead of clipping.
- **`docs/KNOWN_ISSUES.md`** (new file): a standing, concise record of currently unresolved bugs — symptom, what's been tried and ruled out, and the next concrete diagnostic step. Created so open issues don't have to be re-investigated from scratch later.
- Settings page now visibly greys out "Automatically download and install updates" and "Notify me about updates" whenever "Enable update checks" is off, and force-unchecks both if they were checked — making the dependency between these three settings impossible to misconfigure.

### Changed
- **Renamed the "System" page to "Settings"** throughout: `config/registries.py`, `gui/pages/settings_page.py` (replacing `gui/pages/system_page.py`), and the sidebar. `"System"` is kept only as a backward-compatible page-name alias.
- **Settings moved to its own bottom-pinned sidebar section** (`gui/components/sidebar.py`), separated from the main nav (Dashboard/Frameworks/Results/Archive) by an expanding spacer and a thin divider line, instead of sitting in the same list as content pages.
- **Default window size reduced from 1220x780 to 800x600** (`config/runtime.py` `DEFAULT_SETTINGS`), so the app opens at a reasonable size instead of dominating the screen. `MIN_WINDOW_WIDTH`/`MIN_WINDOW_HEIGHT` (both in `config/runtime.py` and the hardcoded `self.minsize()` in `gui/main_window.py`) were lowered from 1060x700 to match — otherwise either floor would have silently clamped the new default back up.
- **Reordered the Updates card**: "Notify me about updates" moved down to sit directly above the "Check Updates" button, since that's the exact moment its Yes/No prompt actually fires. Order is now: Enable update checks → Automatically download and install updates → Notify me about updates → Check Updates.
- **Rewrote all Updates section copy** in plain, user-facing language instead of dense technical paragraphs.
- **"Notify me about updates" now governs two things, not one**: the pre-download Yes/No prompt (manual path) *and* whether the post-install changelog popup appears (automatic path). Turning it off makes both silent — the only sign an update happened is the version number itself, the next time Settings is opened.
- **"Install Update" button removed entirely.** Installation now only ever happens via the Yes/No prompt or full auto-install; there is no longer a separate manual install step to keep in sync with the rest of the flow.
- Mouse wheel scrolling architecture substantially reworked across `gui/components/page_helpers.py` and `gui/main_window.py` — see Fixed section below for the full, documented history (FIX 1 through FIX 7).
- Every Python file touched this cycle now begins with a full top-of-file documentation header (file path, purpose, what talks to it / what it talks to, explanation of every setting/parameter and its edge-case behavior) instead of a one-line comment, per new standing convention. Fix/bug history inside those headers is ordered chronologically, oldest first.

### Fixed
- **Fixed a startup crash** (`AttributeError`/`ImportError`) caused by a stale `gui/pages/system_page.py` still wired to `app.install_update`, a method that had already been removed from `controllers/system_controller.py`.
- **Fixed `config/registries.py` registering the wrong Settings page module** (`system_page` vs. the corrected `system`, and later a naming-convention swap back to `settings_page`) — the broken pre-refactor page was rendering instead of the intended one.
- **Fixed the automatic startup update check silently contacting the registry** even when both "Automatically download and install updates" and "Notify me about updates" were off. `services/updater/gui_integration.py`'s `should_run_automatic_startup_check()` now makes this a true no-op in that combination — the manual "Check Updates" button remains the only way to trigger a check.
- **Fixed mouse wheel scrolling not working anywhere except the Scrollbar itself** for a physical mouse wheel — root-caused and fixed in stages (all documented in full inside `gui/components/page_helpers.py` and `gui/main_window.py`):
  - FIX 1: hover-gated `<Enter>`/`<Leave>` binding never worked because the canvas is fully covered by its own child widgets.
  - FIX 2: `event.delta` truncation meant trackpad-style small deltas (below 120) silently produced zero scroll.
  - FIX 3/4: a focus-based theory (Windows routing `<MouseWheel>` by keyboard focus) proved insufficient.
  - FIX 5: direct per-widget instance binding fixed physical mouse wheel scrolling completely.
  - FIX 6: a global root-level handler resolving the real widget under the cursor via `winfo_containing(event.x_root, event.y_root)` — bypassing Tk's internal motion-cache — was implemented as the current best mechanism for the general page area.
- **Fixed "Update output" and "Activity Log" text boxes swallowing the mouse wheel entirely** whenever their own content already fit fully on screen (FIX 7): Tk's built-in Text-widget scroll binding was intercepting and discarding the event even with nothing to scroll internally, blocking it from ever reaching the page underneath. New `bind_text_widget_scroll_passthrough()` helper forwards the scroll to the page in that specific case.
- **Fixed page text clipping instead of wrapping** on narrower window sizes (see Added: Dynamic text wraplength).

### Known Issues (see `docs/KNOWN_ISSUES.md` for full detail)
- **Touchpad scrolling over the general page area remains unresolved.** A physical mouse wheel works everywhere on the page (FIX 5/6 above); a touchpad two-finger scroll gesture still does not scroll anything outside the Scrollbar itself. Five fix attempts have been made and ruled out; current status, confirmed environment details, and the next concrete diagnostic step are tracked in `docs/KNOWN_ISSUES.md`.

---

## [0.7.0 ALPHA] - 2026-08-16

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

## [0.6.0 ALPHA] - 2026-08-16

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

## [0.5.0] - 2026-08-16

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
