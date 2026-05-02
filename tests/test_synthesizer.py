import pytest
import sqlite3
from unittest.mock import patch
from coreader.synthesizer import build_synthesis_prompt, run_compare_session
from coreader.db import init_db, add_book, update_progress, get_exchanges


def test_synthesis_prompt_includes_current_book():
    prompt = build_synthesis_prompt(
        current_title="Sapiens",
        current_summary="Humanity's cognitive revolution.",
        other_books=[
            {"title": "Atomic Habits", "summary": "Small habits compound."},
        ]
    )
    assert "Sapiens" in prompt
    assert "Humanity's cognitive revolution." in prompt


def test_synthesis_prompt_includes_other_books():
    prompt = build_synthesis_prompt(
        current_title="Sapiens",
        current_summary="Cognitive revolution.",
        other_books=[
            {"title": "Atomic Habits", "summary": "Small habits compound."},
            {"title": "Thus Spake Zarathustra", "summary": "Will to power."},
        ]
    )
    assert "Atomic Habits" in prompt
    assert "Thus Spake Zarathustra" in prompt


def test_synthesis_prompt_requests_connections():
    prompt = build_synthesis_prompt(
        current_title="Sapiens",
        current_summary="Cognitive revolution.",
        other_books=[]
    )
    assert "connection" in prompt.lower() or "connect" in prompt.lower()


@pytest.fixture
def compare_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    # Current book
    book_id = add_book(conn, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    update_progress(conn, book_id, last_chapter=3, rolling_summary="Humanity evolved cognitively.")
    # Another completed book
    other_id = add_book(conn, title="Atomic Habits", author="Clear", book_type="nonfiction", file_path="/tmp/a.epub")
    update_progress(conn, other_id, last_chapter=5, rolling_summary="Small habits compound over time.")
    yield conn, book_id
    conn.close()


def test_run_compare_session_creates_session(compare_db):
    conn, book_id = compare_db
    with patch("coreader.synthesizer.stream_print", return_value="Interesting connection."), \
         patch("builtins.input", side_effect=["Tell me more.", "done"]):
        run_compare_session(conn, book_id=book_id, book_title="Sapiens")

    sessions = conn.execute("SELECT * FROM sessions WHERE book_id=? AND type='compare'", (book_id,)).fetchall()
    assert len(sessions) == 1


def test_run_compare_session_stores_exchanges(compare_db):
    conn, book_id = compare_db
    with patch("coreader.synthesizer.stream_print", return_value="A connection."), \
         patch("builtins.input", side_effect=["Agree!", "done"]):
        run_compare_session(conn, book_id=book_id, book_title="Sapiens")

    sessions = conn.execute("SELECT * FROM sessions WHERE book_id=?", (book_id,)).fetchall()
    exchanges = get_exchanges(conn, sessions[0]["id"])
    assert len(exchanges) >= 2
