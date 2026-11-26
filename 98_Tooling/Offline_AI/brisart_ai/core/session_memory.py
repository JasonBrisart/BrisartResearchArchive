"""
File: brisart_ai/core/session_memory.py

Purpose
-------
Keep compact conversation topics in the local database.

Compact conversation context is retained separately from full indexed documents. The
module records short topic strings rather than reconstructing a complete conversational
model.

Public operations: SessionMemory.add (self, role, content); SessionMemory.recent_topics
(self, limit=6); SessionMemory.close (self).

Internal helpers include SessionMemory.__init__, SessionMemory._compress.

Communication / relationships
-----------------------------
The service opens the handle; conversation code reads and records topics.

Both answers and questions may contribute context, but ordering is by timestamp and
insertion ID so messages recorded within the same second remain deterministic.

Direct project imports: brisart_ai.io.input_cleaner, brisart_ai.util.

Direct importing modules include brisart_ai/core/service.py,
brisart_ai/core/tests/test_conversation.py,
brisart_ai/core/tests/test_session_memory.py.

Concrete calls within this file include sqlite3.connect, self.conn.execute,
self.conn.commit, self._compress, self.conn.close.

Settings / parameters
---------------------
Keeps the first 12 tokens or a 140-character fallback; recent_topics defaults to six
rows.

Call signatures: SessionMemory.add(self, role, content);
SessionMemory.recent_topics(self, limit=6); SessionMemory.close(self).

Edge cases
----------
Blank messages are skipped; insertion ID breaks ties within a timestamp.

Blank or repeated text is not useful topic evidence. Compaction and a bounded
recent-history query keep this layer from becoming a second search engine.

No explicit exception-handling branch is defined at module level. Unexpected errors
therefore follow the caller’s normal error boundary unless a lower-level helper handles
them.

Known limitations
-----------------
This is persistent topic memory, not a complete conversation transcript.

The responsibilities listed here describe the current implementation, not a promise of general
language understanding, platform coverage, or exhaustive validation. Any broader behavior
depends on the documented upstream inputs and downstream consumers. No compatibility adapter
or speculative extension point has been added as part of this pass.

Examples
--------
memory.recent_topics(limit=3)

Other callable entry points in this module include SessionMemory.recent_topics,
SessionMemory.close.
"""

from __future__ import annotations

import re
import sqlite3
from typing import List

from brisart_ai.io.input_cleaner import normalize_shellish_input
from brisart_ai.util import now_ts, tokenize


class SessionMemory:
    """SQLite-backed compact session memory."""

    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        self.conn.commit()

    def _compress(self, role: str, content: str) -> str:
        content = normalize_shellish_input(content.strip())
        content = re.sub(r"\s+", " ", content)
        terms = tokenize(content)
        if terms:
            return " ".join(terms[:12])
        return content[:140]

    def add(self, role: str, content: str) -> None:
        compact = self._compress(role, content)
        if not compact:
            return
        with self.conn:
            self.conn.execute(
                "INSERT INTO conversation_memory(role, content, created_at) VALUES(?,?,?)",
                (role, compact[:400], now_ts()),
            )

    def recent_topics(self, limit: int = 6) -> List[str]:
        rows = self.conn.execute(
            "SELECT content FROM conversation_memory ORDER BY created_at DESC, id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        topics = []
        seen = set()
        for (content,) in rows:
            clipped = " ".join(content.split())[:120]
            if clipped and clipped not in seen:
                seen.add(clipped)
                topics.append(clipped)
        return topics

    def close(self) -> None:
        self.conn.close()

