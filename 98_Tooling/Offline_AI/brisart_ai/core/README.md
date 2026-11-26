# Core

This folder coordinates application services, conversation state, user settings, and session memory. Its service layer is shared by the desktop and command-line entry points.

It does not own file parsing, evidence ranking, or Tk widgets. Those responsibilities belong to the adjacent `io/`, `knowledge/`, and `ui/` folders.

## Files and behavior

`service.py` coordinates CLI and desktop operations, including source removal and source notes with verified excerpts; `conversation.py` answers questions using only enabled local files and notes; `session_memory.py` records conversation context; `settings.py` persists the two local evidence toggles. `tests/` exercises these responsibilities without the Tk desktop. No automatic or explicit web research is available.
