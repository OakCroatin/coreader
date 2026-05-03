import sqlite3
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
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
