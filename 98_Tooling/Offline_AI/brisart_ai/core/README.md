# Core

The core folder coordinates application operations used by both the Tk desktop and CLI. It manages service access, local conversation state and settings, but delegates file extraction and evidence decisions to their domain owners.

## Modules

- `service.py`: Opens application resources, coordinates imports, source management and notes, and checkpoints encrypted-library mutations.
- `encrypted_library.py`: Owns encrypted-at-rest migration, DPAPI automatic unlock, recovery markers and temporary working-copy cleanup.
- `conversation.py`: Applies enabled source scope, invokes retrieval and formats the resulting answer through the knowledge layer.
- `session_memory.py`: Stores compact conversation history separately from the indexed source text.
- `settings.py`: Loads and saves local evidence-source preferences.
- `tests/`: Verifies conversation, service, settings and memory behavior without requiring the desktop.

## Ownership boundaries

The core does not parse document formats, score evidence or build Tk widgets. Those operations are owned by `io/`, `knowledge/` and `ui/`, respectively. The core's settings are not a replacement for the SQLite source index.

## Service lifecycle

The service opens the local resources required by the active operation and coordinates access from the desktop or CLI. Source imports are submitted to the ingestion layer, while source removal and note operations are directed through the owning storage interfaces. This keeps callers from depending on the internal SQLite representation.

Conversation coordination applies enabled evidence sources before invoking retrieval. The answer path does not fetch arbitrary internet material. If a scope excludes a source type, that source type should not contribute an answer merely because a relevant passage exists in the index.

## State responsibilities

Settings describe user choices, while session memory records compact conversation context. Neither is an alternative copy of indexed file text. A research note is independently stored evidence, so removing a source entry is not equivalent to deleting a note snapshot.

For service changes, test both the normal path and the boundary where an operation fails or is interrupted. The desktop must remain responsive, and the CLI should receive a usable error rather than relying on a Tk dialog.

