# BrisartAI

This folder is the BrisartAI application package. It contains the shared application services, local input handling, retrieval engine, state helpers, desktop interface, and their tests. The root launchers live outside this package.

The `core/`, `io/`, `knowledge/`, and `ui/` subfolders own distinct responsibilities; this package README describes their boundaries rather than claiming that the package itself is only a desktop interface.

## Files and behavior

`sidebar.py` groups Library and Preferences actions and shows offline file and note counts. `app.py` shows the active search scope and delivers worker results through a queue on the Tk thread. `chat_panel.py` preserves drafts while searches run. `dialogs.py` handles imports, source management, notes and settings. `windows_drop.py` bridges Explorer drops; Browse is available without it. `theme.py` owns visual constants.
