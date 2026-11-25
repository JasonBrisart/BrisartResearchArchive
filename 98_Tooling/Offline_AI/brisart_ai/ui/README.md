# Desktop interface

`app.py` coordinates the Tk desktop and answer worker. `sidebar.py` opens Add Sources, Remove Sources, Add Note, Settings and Help. `dialogs.py` owns the import queue, source removal, indexed-text note composer and settings controls. `windows_drop.py` forwards Windows Explorer drops to the import queue. `chat_panel.py` handles questions and the transcript; `theme.py` owns visual constants. Browse works without the Windows drop bridge. The desktop never performs internet research.
