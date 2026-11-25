# brisart_ai/ui/

This folder builds the Tk desktop. `app.py` coordinates user actions; `chat_panel.py`, `sidebar.py` and `dialogs.py` build the parts of the window; `theme.py` keeps presentation constants together. Research behavior belongs to the service, not the widgets.

## `app.py`

**Window.** Titled `BrisartAI <version>`, 980 by 640 pixels and no smaller than 760 by 480, with the sidebar on the left and the chat panel filling the rest. It opens with a ready message in the transcript.

**Startup.** `BrisartApp` creates its `BrisartService` before it creates the Tk window, so a database that cannot be opened raises before any window exists. `run(db_path=DEFAULT_DB)` catches that one failure and shows an error dialog that names the likely causes, another running copy or a read-only or inaccessible data folder, then returns. Nothing else catches startup errors.

**Asking a question.** Text typed in the chat box is added to the transcript and answered on a background thread, so the window keeps repainting. The answer is handed back to the main thread, appended, followed by any diagnostic lines the service captured, and the status line is refreshed. A question typed while one is still running appears in the transcript but is not answered or queued. If answering raises, the transcript shows "Something went wrong answering that: ..." and the window carries on.

**Sidebar actions.**

| Button | What happens |
|---|---|
| Import Files | Asks for a folder, or a single file if the folder dialog is cancelled, and indexes it; the window waits until that finishes |
| Add Note | Asks for a title, then the note text; a cancelled or empty prompt saves nothing |
| Research Web | Asks for a question and answers it with a web search forced on |
| Settings | Opens the settings dialog |
| Help | Prints the help text into the transcript |

Closing the window closes the service first.

---

## `chat_panel.py`

`ChatPanel(master, on_submit)` is a read-only, scrolling transcript above a single-line input. Enter or the Send button calls `on_submit(text)` with the trimmed text and clears the box; empty input is ignored. `append_user`, `append_assistant` and `append_system` add a message in the matching style, separated by a blank line, and scroll to the end. `focus_input()` puts the cursor in the box.

---

## `sidebar.py`

`Sidebar(master, actions)` shows the application name and version, the five buttons in the table above, and a status line at the bottom. `actions` maps the button keys `import`, `note`, `research`, `settings` and `help` to functions. `set_status(total, files, web)` shows `Indexed: N (F local, W web)`; it displays only the numbers it is given.

---

## `dialogs.py`

| Function or class | Behavior |
|---|---|
| `ask_import_path(master)` | A folder picker, then a file picker if no folder was chosen; returns `""` if both are cancelled |
| `ask_text(master, title, prompt)` | A one-line prompt; `""` on cancel |
| `ask_note(master)` | A title prompt then a text prompt; `("", "")` on cancel |
| `SettingsDialog(master, service, on_change=None)` | One checkbox per research setting. Each click writes to the live settings and calls `on_change` |

The dialog also carries a short note explaining what the three settings do.

---

## `theme.py`

Constants only, with no Tk import, so importing it needs no display: background colors (`BG_*`), text and accent colors (`FG_*`), `BORDER`, font tuples (`FONT_*`), the spacing values `PAD` and `PAD_SMALL`, and `SIDEBAR_WIDTH` (210). The palette is dark.

---

## `tests/`

`test_theme.py` checks that the colors are `#RRGGBB` strings, the fonts are family and size tuples, the bold fonts are bold, the spacing values are positive, and the module has no Tk import. The other files in this folder need a live display and are checked by running the application.
