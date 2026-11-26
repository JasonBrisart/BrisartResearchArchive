# UI

This folder owns the Tk desktop workspace, navigation, search composer, dialogs, visual theme, and Windows file-drop integration. It displays results and progress supplied by the application service.

Import cancellation and search status are coordinated by the app while background workers handle file preparation. The UI does not independently score retrieval evidence or write directly to the index.

## Files and behavior

`app.py` owns window composition, active search scope and worker lifecycle. `sidebar.py` owns the library actions and counts. `chat_panel.py` owns the query and the Results and Activity views. `dialogs.py` owns library management and settings, with Windows drop support in `windows_drop.py`. `theme.py` supplies the desktop palette without initializing Tk.

During imports `app.py` runs the service off the Tk thread and polls the latest counts; `dialogs.py` displays progress and keeps the completion summary open. `import_progress.py` formats elapsed time and estimates without Tk. The app owns the import cancellation prompt and stop signal; the import dialog forwards close requests as cancellation while running, without exiting the app. During cancellation, the dialog hides live progress, labels the retained selection for retry, and shows final counts only after safe worker cleanup.
