"""Persistent, on-device conversation history for JARVIS Local."""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "did", "does", "for", "from",
    "have", "help", "here", "how", "into", "just", "like", "make", "me", "more",
    "most", "my", "our", "please", "said", "tell", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "what", "when", "where",
    "which", "who", "with", "would", "you", "your",
}
MEMORY_INTENT = re.compile(
    r"\b(remember|recall|previous|last time|before|earlier|we discussed|we talked|"
    r"conversation|what did we|what have we|do you remember)\b", re.I,
)


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class MemoryStore:
    """Stores complete conversation transcripts in a local SQLite database."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()
        if not self.list_sessions():
            self.create_session()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL DEFAULT 'New conversation',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS messages_session_order
                    ON messages(session_id, id);
                CREATE INDEX IF NOT EXISTS sessions_updated
                    ON sessions(updated_at DESC);
                CREATE TABLE IF NOT EXISTS learned_knowledge (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_name TEXT NOT NULL DEFAULT 'voice note',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS knowledge_created ON learned_knowledge(created_at DESC);
                """
            )

    def save_knowledge(self, title: str, content: str, source_name: str = "voice note") -> int:
        """Remember deliberately taught, user-provided text locally (no model training)."""
        title = " ".join(title.split())[:120] or "Learned note"
        content = content.strip()
        if not content:
            raise ValueError("Knowledge text cannot be empty.")
        if len(content) > 20_000:
            raise ValueError("A learned note is limited to 20,000 characters.")
        stamp = now_utc()
        with self._connect() as db:
            result = db.execute(
                "INSERT INTO learned_knowledge(title,content,source_name,created_at) VALUES(?,?,?,?)",
                (title, content, Path(source_name).name[:160], stamp),
            )
            return int(result.lastrowid)

    def save_knowledge_document(self, filename: str, content: str) -> int:
        """Store a locally selected text file in bounded chunks, keeping only its base name."""
        text = content.strip()
        if not text:
            raise ValueError("The selected file contains no readable text.")
        if len(text) > 200_000:
            raise ValueError("Files larger than 200,000 characters cannot be added to local memory.")
        name = Path(filename).name[:120] or "local file"
        chunks = [text[index:index + 5000] for index in range(0, len(text), 5000)]
        stamp = now_utc()
        with self._connect() as db:
            for index, chunk in enumerate(chunks, start=1):
                title = name if len(chunks) == 1 else f"{name} (part {index}/{len(chunks)})"
                db.execute(
                    "INSERT INTO learned_knowledge(title,content,source_name,created_at) VALUES(?,?,?,?)",
                    (title, chunk, name, stamp),
                )
            return len(chunks)

    def learned_knowledge(self, limit: int = 30) -> list[dict[str, str]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT title,content,source_name,created_at FROM learned_knowledge ORDER BY id DESC LIMIT ?",
                (max(1, min(int(limit), 500)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_session(self, title: str = "New conversation") -> str:
        session_id = str(uuid.uuid4())
        stamp = now_utc()
        with self._connect() as db:
            db.execute(
                "INSERT INTO sessions(id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title.strip()[:80] or "New conversation", stamp, stamp),
            )
        return session_id

    def list_sessions(self) -> list[dict[str, str]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT s.id, s.title, s.created_at, s.updated_at, "
                "(SELECT content FROM messages m WHERE m.session_id=s.id AND m.role='user' "
                "ORDER BY m.id LIMIT 1) AS preview "
                "FROM sessions s ORDER BY s.updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def save_exchange(self, session_id: str, user_text: str, assistant_text: str) -> None:
        """Save both sides atomically and title a new session from its first user message."""
        stamp = now_utc()
        with self._connect() as db:
            session = db.execute("SELECT title FROM sessions WHERE id=?", (session_id,)).fetchone()
            if session is None:
                raise KeyError(f"Unknown conversation id: {session_id}")
            db.executemany(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                [(session_id, "user", user_text, stamp),
                 (session_id, "assistant", assistant_text, stamp)],
            )
            title = session["title"]
            if title == "New conversation":
                title = re.sub(r"\s+", " ", user_text).strip()[:60] or title
            db.execute("UPDATE sessions SET title=?, updated_at=? WHERE id=?", (title, stamp, session_id))

    def save_message(self, session_id: str, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        stamp = now_utc()
        with self._connect() as db:
            db.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, stamp),
            )
            db.execute("UPDATE sessions SET updated_at=? WHERE id=?", (stamp, session_id))

    def messages(self, session_id: str, limit: int | None = None) -> list[dict[str, str]]:
        query = "SELECT role, content, created_at FROM messages WHERE session_id=? ORDER BY id"
        parameters: tuple[object, ...] = (session_id,)
        if limit is not None:
            query = (
                "SELECT role, content, created_at FROM "
                f"(SELECT role, content, created_at, id FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?) "
                "ORDER BY id"
            )
            parameters = (session_id, max(1, int(limit)))
        with self._connect() as db:
            rows = db.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    @staticmethod
    def _terms(text: str) -> list[str]:
        return [word for word in re.findall(r"[a-z0-9]{3,}", text.lower()) if word not in STOP_WORDS]

    def relevant_context(self, query: str, max_chars: int = 2400) -> str:
        """Return concise saved excerpts relevant to a prompt, without sending data anywhere."""
        terms = list(dict.fromkeys(self._terms(query)))
        if not terms:
            return ""
        with self._connect() as db:
            rows = db.execute(
                "SELECT m.session_id, m.role, m.content, m.id, s.title "
                "FROM messages m JOIN sessions s ON s.id=m.session_id "
                "ORDER BY m.id DESC"
            ).fetchall()

        # For explicit memory questions, surface the most recent earlier exchanges even if
        # the question contains no distinctive subject words.
        matching = []
        for row in rows:
            content_terms = set(self._terms(row["content"]))
            score = sum(term in content_terms for term in terms)
            if score:
                matching.append((score, row))
        matching.sort(key=lambda item: (item[0], item[1]["id"]), reverse=True)
        matching = [row for _, row in matching]
        if not matching and MEMORY_INTENT.search(query):
            matching = rows

        output: list[str] = []
        used: set[tuple[str, int]] = set()
        for row in matching:
            key = (row["session_id"], row["id"])
            if key in used:
                continue
            used.add(key)
            excerpt = re.sub(r"\s+", " ", row["content"]).strip()
            line = f"[{row['title']} / {row['role']}] {excerpt}"
            if sum(len(part) + 1 for part in output) + len(line) > max_chars:
                break
            output.append(line)
            if len(output) >= 8:
                break
        with self._connect() as db:
            knowledge_rows = db.execute(
                "SELECT id,title,content,source_name FROM learned_knowledge ORDER BY id DESC"
            ).fetchall()
        ranked_knowledge = []
        for row in knowledge_rows:
            body_terms = set(self._terms(row["title"] + " " + row["content"]))
            score = sum(term in body_terms for term in terms)
            if score:
                ranked_knowledge.append((score, row))
        ranked_knowledge.sort(key=lambda pair: (pair[0], pair[1]["id"]), reverse=True)
        for _, row in ranked_knowledge:
            excerpt = re.sub(r"\s+", " ", row["content"]).strip()
            line = f"[learned locally: {row['title']}] {excerpt}"
            used_size = sum(len(part) + 1 for part in output)
            if used_size + len(line) > max_chars:
                continue
            output.append(line)
            if len(output) >= 12:
                break
        return "\n".join(output)

    def search_messages(self, query: str, limit: int = 200) -> list[dict[str, str]]:
        """Search all saved transcripts by literal case-insensitive substring."""
        query = query.strip()
        if not query:
            return []
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._connect() as db:
            rows = db.execute(
                "SELECT m.session_id, m.role, m.content, m.created_at, s.title "
                "FROM messages m JOIN sessions s ON s.id=m.session_id "
                "WHERE m.content LIKE ? ESCAPE '\\' ORDER BY m.id DESC LIMIT ?",
                (f"%{escaped}%", max(1, int(limit))),
            ).fetchall()
        return [dict(row) for row in rows]
