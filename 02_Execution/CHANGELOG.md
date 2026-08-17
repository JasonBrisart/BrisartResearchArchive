# Changelog

All notable changes to Brisart Research Archive are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
