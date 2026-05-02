from coreader.db import (
    add_book, get_book_by_title, add_chapter, get_chapter,
    get_progress, update_progress, add_session, add_exchange,
    get_exchanges, list_books
)

def test_add_and_retrieve_book(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/sapiens.epub")
    book = get_book_by_title(db, "Sapiens")
    assert book["title"] == "Sapiens"
    assert book["type"] == "nonfiction"

def test_add_and_retrieve_chapter(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    book = get_book_by_title(db, "Sapiens")
    add_chapter(db, book_id=book["id"], number=1, title="Ch 1", text="Chapter one text.")
    ch = get_chapter(db, book_id=book["id"], number=1)
    assert ch["text"] == "Chapter one text."

def test_progress_defaults_to_empty(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    book = get_book_by_title(db, "Sapiens")
    progress = get_progress(db, book["id"])
    assert progress["last_chapter"] == 0
    assert progress["rolling_summary"] == ""

def test_update_progress(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    book = get_book_by_title(db, "Sapiens")
    update_progress(db, book["id"], last_chapter=3, rolling_summary="Summary so far.")
    progress = get_progress(db, book["id"])
    assert progress["last_chapter"] == 3
    assert progress["rolling_summary"] == "Summary so far."

def test_session_and_exchanges(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    book = get_book_by_title(db, "Sapiens")
    session_id = add_session(db, book_id=book["id"], chapter=2, session_type="checkin")
    add_exchange(db, session_id=session_id, role="assistant", content="What struck you?", seq=1)
    add_exchange(db, session_id=session_id, role="user", content="The timeline.", seq=2)
    exchanges = get_exchanges(db, session_id)
    assert len(exchanges) == 2
    assert exchanges[0]["role"] == "assistant"

def test_list_books(db):
    add_book(db, title="Sapiens", author="Harari", book_type="nonfiction", file_path="/tmp/s.epub")
    add_book(db, title="Dune", author="Herbert", book_type="fiction", file_path="/tmp/dune.epub")
    books = list_books(db)
    assert len(books) == 2
