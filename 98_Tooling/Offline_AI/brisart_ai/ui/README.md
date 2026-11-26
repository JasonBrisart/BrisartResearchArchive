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

## Query workflow

The workspace keeps the question composer distinct from the Results and Activity views. Results presents answers and cited passages; Activity records operational events such as imports and diagnostics. Search scope remains visible so users can understand whether files, notes, or both are eligible evidence.

The application owns service calls and marshals worker results back to Tk. UI components should not call index mutation functions independently or update widgets from a worker thread. The sidebar and dialogs are presentation and interaction boundaries rather than competing implementations of library management.

## Import progress and cancellation

The import dialog first discovers eligible files and then displays a determinate progress bar, processed and remaining counts, elapsed time, and an estimated time left. Estimated time is based on observed throughput and can change as file costs differ. A skipped or failed file may be processed without increasing the indexed count.

Canceling an import requests cooperative shutdown. The current selected file may finish, and dispatched worker preparation must be drained safely. During that interval, the UI shows a stopping state rather than continuing to animate import progress. Completion keeps the app open and preserves previously indexed sources.

## Platform and accessibility boundaries

The desktop uses Tk and supports file browsing independently of optional Windows drop integration. Keyboard focus and modal dialogs must not interfere with each other. UI regression tests cover nonvisual logic where possible, but a Windows smoke test is still required to verify actual layout and focus behavior.

