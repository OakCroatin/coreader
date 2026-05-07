"""
db.py — SQLite database setup and all query functions.

The database lives at ~/.coreader/coreader.db. It stores five tables:
  books     — one row per ingested book
  chapters  — all extracted chapter text, linked to a book
  progress  — tracks last chapter read and the rolling summary per book
  sessions  — one row per checkin or compare session
  exchanges — individual messages within a session (assistant + user turns)

All writes go through this module. No other file touches the database directly.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Database file location — outside the project so it survives reinstalls
DB_PATH = Path.home() / ".coreader" / "coreader.db"


def get_connection(path: Path = DB_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite database and return a connection.

    Creates the parent directory if needed. Enables foreign key enforcement
    and sets row_factory so rows can be accessed by column name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row  # allows row["column_name"] access
    conn.execute("PRAGMA foreign_keys = ON")  # enforce referential integrity
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables if they don't already exist.

    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS.
    """
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id          INTEGER PRIMARY KEY,
            title       TEXT NOT NULL,
            author      TEXT,
            type        TEXT NOT NULL CHECK(type IN ('fiction', 'nonfiction')),
            file_path   TEXT,
            added_date  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS chapters (
            id          INTEGER PRIMARY KEY,
            book_id     INTEGER NOT NULL REFERENCES books(id),
            number      INTEGER NOT NULL,
            title       TEXT,
            text        TEXT NOT NULL
        );

        -- Tracks reading progress and the rolling LLM-generated summary
        CREATE TABLE IF NOT EXISTS progress (
            book_id         INTEGER PRIMARY KEY REFERENCES books(id),
            last_chapter    INTEGER NOT NULL DEFAULT 0,
            rolling_summary TEXT NOT NULL DEFAULT '',
            updated_at      TEXT NOT NULL
        );

        -- One row per checkin or compare session
        CREATE TABLE IF NOT EXISTS sessions (
            id          INTEGER PRIMARY KEY,
            book_id     INTEGER NOT NULL REFERENCES books(id),
            chapter     INTEGER,
            type        TEXT NOT NULL CHECK(type IN ('checkin', 'compare')),
            timestamp   TEXT NOT NULL
        );

        -- Individual turns within a session, ordered by seq
        CREATE TABLE IF NOT EXISTS exchanges (
            id          INTEGER PRIMARY KEY,
            session_id  INTEGER NOT NULL REFERENCES sessions(id),
            role        TEXT NOT NULL CHECK(role IN ('assistant', 'user')),
            content     TEXT NOT NULL,
            seq         INTEGER NOT NULL
        );
    """)
    conn.commit()


def _now() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def add_book(conn, title: str, author: str, book_type: str, file_path: str) -> int:
    """Insert a new book and create its initial progress row.

    Returns the new book's id.
    """
    cur = conn.execute(
        "INSERT INTO books (title, author, type, file_path, added_date) VALUES (?,?,?,?,?)",
        (title, author, book_type, file_path, _now())
    )
    # Create a blank progress row so get_progress never returns None for a known book
    conn.execute(
        "INSERT INTO progress (book_id, last_chapter, rolling_summary, updated_at) VALUES (?,0,'',?)",
        (cur.lastrowid, _now())
    )
    conn.commit()
    return cur.lastrowid


def get_book_by_title(conn, title: str):
    """Return the book row matching the title (case-insensitive), or None if not found."""
    return conn.execute(
        "SELECT * FROM books WHERE title = ? COLLATE NOCASE", (title,)
    ).fetchone()


def list_books(conn):
    """Return all books ordered by most recently added."""
    return conn.execute("SELECT * FROM books ORDER BY added_date DESC").fetchall()


def add_chapter(conn, book_id: int, number: int, title: str, text: str) -> int:
    """Insert a single chapter row and return its id."""
    cur = conn.execute(
        "INSERT INTO chapters (book_id, number, title, text) VALUES (?,?,?,?)",
        (book_id, number, title, text)
    )
    conn.commit()
    return cur.lastrowid


def get_chapter(conn, book_id: int, number: int):
    """Return a chapter row by book and chapter number, or None."""
    return conn.execute(
        "SELECT * FROM chapters WHERE book_id = ? AND number = ?", (book_id, number)
    ).fetchone()


def get_chapter_count(conn, book_id: int) -> int:
    """Return the total number of chapters stored for a book."""
    row = conn.execute("SELECT COUNT(*) FROM chapters WHERE book_id = ?", (book_id,)).fetchone()
    return row[0]


def get_progress(conn, book_id: int):
    """Return the progress row for a book (last chapter + rolling summary)."""
    return conn.execute("SELECT * FROM progress WHERE book_id = ?", (book_id,)).fetchone()


def update_progress(conn, book_id: int, last_chapter: int, rolling_summary: str) -> None:
    """Update the last chapter read and rolling summary after a checkin session."""
    conn.execute(
        "UPDATE progress SET last_chapter=?, rolling_summary=?, updated_at=? WHERE book_id=?",
        (last_chapter, rolling_summary, _now(), book_id)
    )
    conn.commit()


def add_session(conn, book_id: int, chapter: int | None, session_type: str) -> int:
    """Create a new session record and return its id.

    session_type is either 'checkin' (chapter dialogue) or 'compare' (cross-book synthesis).
    chapter is None for compare sessions.
    """
    cur = conn.execute(
        "INSERT INTO sessions (book_id, chapter, type, timestamp) VALUES (?,?,?,?)",
        (book_id, chapter, session_type, _now())
    )
    conn.commit()
    return cur.lastrowid


def add_exchange(conn, session_id: int, role: str, content: str, seq: int) -> None:
    """Insert one turn (assistant or user message) into a session."""
    conn.execute(
        "INSERT INTO exchanges (session_id, role, content, seq) VALUES (?,?,?,?)",
        (session_id, role, content, seq)
    )
    conn.commit()


def get_exchanges(conn, session_id: int):
    """Return all exchanges for a session in chronological order."""
    return conn.execute(
        "SELECT * FROM exchanges WHERE session_id = ? ORDER BY seq", (session_id,)
    ).fetchall()


def remove_book(conn, book_id: int) -> None:
    """Permanently delete a book and all associated data.

    Deletes in dependency order to satisfy foreign key constraints:
    exchanges → sessions → progress → chapters → book
    """
    # Get all session ids for this book so we can delete their exchanges
    session_ids = [r[0] for r in conn.execute(
        "SELECT id FROM sessions WHERE book_id = ?", (book_id,)
    ).fetchall()]

    for sid in session_ids:
        conn.execute("DELETE FROM exchanges WHERE session_id = ?", (sid,))

    conn.execute("DELETE FROM sessions WHERE book_id = ?", (book_id,))
    conn.execute("DELETE FROM progress WHERE book_id = ?", (book_id,))
    conn.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
