import sqlite3
import pytest
from unittest.mock import patch, MagicMock
from coreader.session import build_checkin_prompt, build_summary_update_prompt, run_checkin_session
from coreader.db import init_db, add_book, add_chapter, get_progress, get_exchanges


def test_checkin_prompt_fiction_includes_chapter_text():
    prompt = build_checkin_prompt(
        book_type="fiction",
        title="Dune",
        chapter_number=3,
        chapter_text="Paul walked into the desert.",
        rolling_summary="Paul arrived on Arrakis."
    )
    assert "Paul walked into the desert." in prompt
    assert "Paul arrived on Arrakis." in prompt
    assert "character" in prompt.lower() or "arc" in prompt.lower()


def test_checkin_prompt_nonfiction_focuses_on_arguments():
    prompt = build_checkin_prompt(
        book_type="nonfiction",
        title="Sapiens",
        chapter_number=2,
        chapter_text="Humans developed agriculture.",
        rolling_summary="Cognitive revolution happened."
    )
    assert "Humans developed agriculture." in prompt
    assert "argument" in prompt.lower() or "framework" in prompt.lower()


def test_summary_update_prompt_includes_all_inputs():
    prompt = build_summary_update_prompt(
        title="Sapiens",
        chapter_number=2,
        chapter_text="Agriculture chapter.",
        rolling_summary="Old summary.",
        dialogue_text="User said: interesting."
    )
    assert "Agriculture chapter." in prompt
    assert "Old summary." in prompt
    assert "User said: interesting." in prompt


@pytest.fixture
def session_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    init_db(conn)
    book_id = add_book(conn, title="Dune", author="Herbert", book_type="fiction", file_path="/tmp/dune.epub")
    add_chapter(conn, book_id=book_id, number=1, title="Chapter 1", text="Paul walked into the desert.")
    yield conn, book_id
    conn.close()


def test_run_checkin_session_creates_session_and_exchanges(session_db):
    conn, book_id = session_db
    with patch("coreader.session.stream_print", return_value="What do you think of Paul?") as mock_stream, \
         patch("coreader.session.chat", return_value="Good summary.") as mock_chat, \
         patch("builtins.input", side_effect=["He seems lost.", "done"]):
        run_checkin_session(conn, book_id=book_id, chapter_number=1, book_title="Dune", book_type="fiction")

    # session was created
    sessions = conn.execute("SELECT * FROM sessions WHERE book_id=?", (book_id,)).fetchall()
    assert len(sessions) == 1
    assert sessions[0]["type"] == "checkin"
    assert sessions[0]["chapter"] == 1

    # exchanges were stored
    exchanges = get_exchanges(conn, sessions[0]["id"])
    assert len(exchanges) >= 2
    roles = [e["role"] for e in exchanges]
    assert "assistant" in roles
    assert "user" in roles


def test_run_checkin_session_updates_rolling_summary(session_db):
    conn, book_id = session_db
    with patch("coreader.session.stream_print", return_value="What do you think?"), \
         patch("coreader.session.chat", return_value="Updated summary text."), \
         patch("builtins.input", side_effect=["Interesting.", "done"]):
        run_checkin_session(conn, book_id=book_id, chapter_number=1, book_title="Dune", book_type="fiction")

    progress = get_progress(conn, book_id)
    assert progress["last_chapter"] == 1
    assert "Updated summary text." in progress["rolling_summary"]


def test_run_checkin_session_missing_chapter_exits_gracefully(session_db):
    conn, book_id = session_db
    # chapter 99 doesn't exist — should print message and return without error
    with patch("builtins.print") as mock_print:
        run_checkin_session(conn, book_id=book_id, chapter_number=99, book_title="Dune", book_type="fiction")
    mock_print.assert_called_once_with("Chapter 99 not found for 'Dune'.")
