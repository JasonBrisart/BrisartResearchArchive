# Architecture

BrisartAI is an offline-first Python research assistant with a Tk desktop and headless CLI. The two entry points share `BrisartService`, and no runtime path initiates public internet search.

## Request flow

1. `run.py` or `cli.py` installs the external native module directory through `brisart_ai/native_path.py`.
2. The service opens the per-user SQLite index, settings and session memory.
3. A question enters `core/conversation.py`, which normalizes it and selects only enabled `file` and `note` source types.
4. `knowledge/ranker.py` ranks indexed evidence, and `knowledge/synthesizer.py` extracts cited passages.
5. The response is returned to the CLI or Tk transcript and recorded in session memory.

When both source toggles are off, the application returns a no-evidence answer rather than falling back to historical web rows.

## Responsibility ownership

- `core/`: orchestration, user preferences and conversation context.
- `io/`: local file enumeration and text extraction, including HTML files already on disk.
- `knowledge/`: local indexing, evidence scoring, citations and notes. The schema can retain historical `web` rows; this release does not migrate or erase user data.
- `ui/`: desktop widgets and user actions, without network ownership.
- `state.py`: user-data location and safe legacy migration.
- `native_path.py`: resolving the shared external Native APIs; it does not contain their implementations.

The former `brisart_ai/web/` subsystem, provider search, crawler, HTTP fetcher, public URL policy and live-search replay script have been removed. This does not change the local document reader's ability to parse downloaded HTML files.

## Boundaries

The root contains only `run.py`, `cli.py` and `version.py`; no `__init__.py` contains code. Application data lives outside the repository. The Native APIs live in `94_Native_API's/Official`, not inside Offline_AI. Changes to their interfaces can affect the application on its next launch.
