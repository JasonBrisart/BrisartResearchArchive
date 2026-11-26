# UI

This folder owns the Tk desktop interface and its interaction with the application service. It displays library counts, questions, evidence, import progress and local settings without independently ranking or persisting source content.

## Workspace components

- `app.py`: Composes the window and coordinates service access, background operations and UI-thread updates.
- `sidebar.py`: Presents library actions, counts and navigation.
- `chat_panel.py`: Owns the query composer and the Results and Activity views.
- `dialogs.py`: Presents source management, import and settings dialogs.
- `import_progress.py`: Formats elapsed time, processed counts and estimates independently of Tk.
- `theme.py`: Defines desktop styling.
- `windows_drop.py`: Bridges supported Windows file drops; browsing remains available without it.
- `tests/`: Exercises UI-adjacent logic and selected interactions.

## Import cancellation and responsiveness

Imports run outside the Tk event loop. The interface polls progress from the service rather than allowing worker threads to manipulate widgets. Confirming **Cancel Import** stops additional work, waits for safe worker cleanup and keeps the application open. The dialog distinguishes an active import from the stopping and completed states.
