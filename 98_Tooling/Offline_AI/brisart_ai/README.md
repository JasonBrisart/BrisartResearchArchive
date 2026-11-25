# Application package

This folder owns shared application behavior. `core/` coordinates questions and settings; `io/` extracts text from local files; `knowledge/` stores and ranks evidence; `ui/` presents the desktop. `native_path.py` locates the shared external API stack, `state.py` owns per-user storage, and `intent.py`, `util.py` and `version_info.py` supply cross-cutting helpers. `tests/` covers these modules and the package layout. There is no network-search subsystem.
