# Core

The core folder coordinates application operations used by both the Tk desktop and CLI. It manages service access, local conversation state and settings, but delegates file extraction and evidence decisions to their domain owners.

## Modules

- `service.py`: Opens application resources and coordinates imports, source management and notes.
- `conversation.py`: Applies enabled source scope, invokes retrieval and formats the resulting answer through the knowledge layer.
- `session_memory.py`: Stores compact conversation history separately from the indexed source text.
- `settings.py`: Loads and saves local evidence-source preferences.
- `tests/`: Verifies conversation, service, settings and memory behavior without requiring the desktop.

## Ownership boundaries

The core does not parse document formats, score evidence or build Tk widgets. Those operations are owned by `io/`, `knowledge/` and `ui/`, respectively. The core's settings are not a replacement for the SQLite source index.
