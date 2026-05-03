import sqlite3
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from coreader.db import init_db, add_book, add_chapter, get_connection
from coreader.web import create_app


@pytest.fixture
def web_db(tmp_path):
    """In-memory DB with one book for web tests."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_db(conn)
    book_id = add_book(conn, title="Dune", author="Herbert", book_type="fiction", file_path="/tmp/dune.epub")
    add_chapter(conn, book_id=book_id, number=1, title="Ch 1", text="Paul walked into the desert.")
    add_chapter(conn, book_id=book_id, number=2, title="Ch 2", text="The worm appeared.")
    return conn, book_id


@pytest.fixture
def client(web_db):
    conn, book_id = web_db
    app = create_app(conn)
    return TestClient(app), book_id


def test_library_page_returns_200(client):
    c, _ = client
    response = c.get("/")
    assert response.status_code == 200
    assert "Dune" in response.text


def test_new_session_form_returns_200(client):
    c, book_id = client
    response = c.get(f"/session/new/{book_id}")
    assert response.status_code == 200
    assert "Dune" in response.text


def test_start_checkin_session_redirects_to_chat(client):
    c, book_id = client
    with patch("coreader.web.chat", return_value="What do you think?"):
        response = c.post("/session/start", data={
            "book_id": book_id,
            "session_type": "checkin",
            "chapter": "1",
        }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/session/" in response.headers["location"]


def test_start_compare_session_redirects_to_chat(client):
    c, book_id = client
    with patch("coreader.web.chat", return_value="Here is a connection."):
        response = c.post("/session/start", data={
            "book_id": book_id,
            "session_type": "compare",
            "chapter": "",
        }, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/session/" in response.headers["location"]


def test_chat_page_returns_200(client):
    """Seed an active session manually and verify the chat page loads."""
    c, book_id = client
    with patch("coreader.web.chat", return_value="Opening question."):
        r = c.post("/session/start", data={
            "book_id": book_id, "session_type": "checkin", "chapter": "1"
        }, follow_redirects=True)
    assert r.status_code == 200
    assert "Opening question." in r.text


def test_send_message_returns_json(client):
    c, book_id = client
    with patch("coreader.web.chat", return_value="Opening question."):
        c.post("/session/start", data={
            "book_id": book_id, "session_type": "checkin", "chapter": "1"
        }, follow_redirects=True)
    # Find the session_id from active_sessions
    from coreader.web import active_sessions
    session_id = list(active_sessions.keys())[-1]

    with patch("coreader.web.chat", return_value="Interesting point."):
        r = c.post(f"/session/{session_id}/message", json={"content": "I think it matters."})
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "assistant"
    assert "Interesting point." in data["content"]
