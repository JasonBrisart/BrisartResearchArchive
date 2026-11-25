# BrisartAI

BrisartAI is a local-first research assistant. It indexes files and notes, then answers with excerpts and citations from that evidence. It does not generate new text to fill gaps. Public-web research is optional and off by default.

## Run it

```bash
python run.py        # the desktop window
python cli.py ...    # the same service, no window
```

BrisartAI requires the seven shared Brisart native modules from the Archive's external `94_Native_API's` folder (preferably `Official/`). For a detached checkout, set `BRISART_NATIVE_API` to the external folder containing the module files. There is no bundled fallback and no network installation step. The window needs Tkinter and a display; `cli.py` needs neither.

In the window, the sidebar has **Import Files**, **Add Note**, **Research Web**, **Settings** and **Help**; type a question in the box and press Enter.

| `cli.py` command | What it does |
|---|---|
| `counts` | Prints how many sources are indexed |
| `ask "question"` | Answers from your index: files and notes as chosen in the Local Files and Research Notes settings, plus pages crawled earlier. Searches the web only with `--web`; the Automatic Web Research setting is not consulted |
| `research "query" [--limit N] [--depth N]` | Searches the web and indexes the pages |
| `import PATH [PATH ...]` | Indexes files and folders |
| `note "Title" "Body"` | Saves a note |
| `notes [--limit N]` | Lists recent notes |

Add `--db PATH` before the command to use a different index file.

---

## Your data

BrisartAI saves two files, in a per-user folder rather than in the project folder, so replacing the program folder to update never touches them:

| System | Folder |
|---|---|
| Windows | `%APPDATA%\Brisart Research Archive\BrisartAI` |
| macOS | `~/Library/Application Support/Brisart Research Archive/BrisartAI` |
| Linux and others | `$XDG_CONFIG_HOME/Brisart Research Archive/BrisartAI`, or `~/.config/...` |

- `brisart_ai_index.sqlite3` holds everything you have imported, crawled or noted, and the recent-question memory.
- `research_settings.json` holds the three research settings.

Set `BRISARTAI_STATE_DIR` to use another folder, for example one on a USB drive. A copy from an earlier release that still has its index beside the program moves it to this folder on the first start. The index is a plain, unencrypted SQLite file, and on Windows the folder is the roaming profile, which a domain can sync between computers.

---

## What it reads

Plain text, markup, configuration and source code in dozens of formats (including Markdown, HTML, CSV, JSON, YAML, TOML, Python, JavaScript, Java, C, C++, C#, Go, Rust, shell scripts and SQL), plus Word, PowerPoint, Excel and OpenDocument text files and PDFs. The full list, and how each type is read, is in [`brisart_ai/io/README.md`](../brisart_ai/io/README.md). PDF extraction is best-effort and finds little in files that store text in an unusual way.

---

## Web research

Off by default. It runs only when you use **Research Web**, `cli.py research` or `cli.py ask --web`, or when you turn on **Automatic Web Research** in Settings, which searches the web when nothing local answers a question. It searches seven public search providers without any account or API key, drops dictionary sites and off-topic results, ranks low-value hosts down, honors `robots.txt`, refuses local and private network addresses, and indexes the pages it keeps. Details are in [`brisart_ai/web/README.md`](../brisart_ai/web/README.md).

---

## How an answer is chosen

Each indexed source is scored for the question by the Brisart Relevance Engine, which weighs how rare each query term is, how often it appears, how long the document is, how many of the query's terms it contains, whether the title matches, whether the exact phrase appears, how close the matched terms are, and what kind of question was asked (who founded, how many, why). The best sentences are then quoted back, numbered, with a source list. The scoring is described in [`brisart_ai/knowledge/README.md`](../brisart_ai/knowledge/README.md).

---

## Project layout

```text
BrisartAI/
├── run.py                 starts the desktop window
├── cli.py                 the command line
├── version.py             the version number
│
├── brisart_ai/            the application
│   ├── core/              the service, answer routing, memory, settings
│   ├── io/                reading files into text
│   ├── knowledge/         the index, ranking, answer synthesis, notes
│   ├── ui/                the Tkinter window
│   ├── web/               web search, fetching and crawling
│   ├── blocklist.py
│   ├── intent.py
│   ├── native_path.py
│   ├── state.py
│   ├── util.py
│   └── version_info.py
│
├── docs/                  this page and the documents below
└── scripts/               the test runner and two replay tools
```

`brisart_ai/`, its application subfolders and `scripts/` have a `README.md` that describes only that folder; a `tests/` folder is described in its parent's. There is no `__init__.py` anywhere.

---

## Documentation

| Document | What it covers |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | How the layers fit together, the path of a question, the dependency rules, where to make a change |
| [`SECURITY.md`](SECURITY.md) | How to report a vulnerability, what is in scope, and the standing caveats |
| [`TESTING.md`](TESTING.md) | How to run the tests, how they are laid out and what they do not cover |
| [`CHANGELOG.md`](CHANGELOG.md) | Release history, newest first |

To run the tests: `python scripts/run_tests.py` (needs `pytest`).
