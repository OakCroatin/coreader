"""
web.py — FastAPI web application for Co-Reader.

Exposes the book library and session dialogue as a browser UI.
All DB and LLM logic is delegated to existing backend modules.

Routes:
  GET  /                          — library list
  GET  /session/new/{book_id}     — start-session form
  POST /session/start             — create session, redirect to chat
  GET  /session/{session_id}      — chat view
  POST /session/{session_id}/message — send message, get response
  POST /session/{session_id}/done    — end session
  DELETE /books/{book_id}         — remove book
"""

import sqlite3
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import ollama

from coreader.db import (
    get_connection, init_db, list_books, get_progress, get_chapter_count,
    get_book_by_title, remove_book, get_chapter, add_session, add_exchange,
    get_exchanges, update_progress,
)
from coreader.session import build_checkin_prompt, build_summary_update_prompt
from coreader.synthesizer import build_synthesis_prompt
from coreader.ollama_client import chat

TEMPLATES_DIR = Path(__file__).parent / "templates"

# In-memory store for active session conversation histories.
# Keyed by session_id (int) -> list of role/content message dicts.
active_sessions: dict[int, list[dict]] = {}


def create_app(conn=None) -> FastAPI:
    """Create and return the FastAPI application.

    Args:
        conn: Optional database connection (used for testing with in-memory DB).
              If None, uses the default ~/.coreader/coreader.db.
    """
    app = FastAPI(title="Co-Reader")
    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

    # If an injected connection is provided (e.g. in-memory test DB), clone it
    # into a new connection with check_same_thread=False so it can be used
    # safely from FastAPI's worker threads / async event loop thread.
    _test_conn: sqlite3.Connection | None = None
    if conn is not None:
        _test_conn = sqlite3.connect(":memory:", check_same_thread=False)
        _test_conn.row_factory = sqlite3.Row
        _test_conn.execute("PRAGMA foreign_keys = ON")
        conn.backup(_test_conn)

    def get_conn():
        """Return the injected test connection or open the real DB."""
        if _test_conn is not None:
            return _test_conn
        c = get_connection()
        init_db(c)
        return c

    @app.get("/", response_class=HTMLResponse)
    def library(request: Request):
        """Library list page — all books with progress."""
        c = get_conn()
        books = list_books(c)
        book_data = []
        for book in books:
            progress = get_progress(c, book["id"])
            total = get_chapter_count(c, book["id"])
            last_ch = progress["last_chapter"] if progress else 0
            updated = progress["updated_at"][:10] if progress and progress["updated_at"] else "—"
            book_data.append({
                "id": book["id"],
                "title": book["title"],
                "author": book["author"],
                "type": book["type"],
                "last_chapter": last_ch,
                "total_chapters": total,
                "last_checkin": updated,
            })
        return templates.TemplateResponse(request, "index.html", {
            "books": book_data,
        })

    @app.get("/session/new/{book_id}", response_class=HTMLResponse)
    async def new_session_form(request: Request, book_id: int):
        """Form page to choose checkin (with chapter number) or compare."""
        c = get_conn()
        books = list_books(c)
        book = next((b for b in books if b["id"] == book_id), None)
        if not book:
            return HTMLResponse("Book not found", status_code=404)
        total = get_chapter_count(c, book_id)
        return templates.TemplateResponse(request, "new_session.html", {
            "book": book,
            "total_chapters": total,
        })

    @app.post("/session/start")
    async def start_session(
        book_id: int = Form(...),
        session_type: str = Form(...),
        chapter: str = Form(""),
    ):
        """Create a new session, build the opening message, store in memory, redirect to chat."""
        c = get_conn()
        books = list_books(c)
        book = next((b for b in books if b["id"] == book_id), None)
        if not book:
            return HTMLResponse("Book not found", status_code=404)

        progress = get_progress(c, book_id)
        rolling_summary = progress["rolling_summary"] if progress else ""

        if session_type == "checkin":
            chapter_num = int(chapter)
            ch = get_chapter(c, book_id, chapter_num)
            if not ch:
                return HTMLResponse(f"Chapter {chapter_num} not found", status_code=404)
            system_prompt = build_checkin_prompt(
                book_type=book["type"],
                title=book["title"],
                chapter_number=chapter_num,
                chapter_text=ch["text"],
                rolling_summary=rolling_summary,
            )
            session_id = add_session(c, book_id=book_id, chapter=chapter_num, session_type="checkin")
        else:
            # compare session — gather other books' summaries
            all_books = list_books(c)
            other_books = []
            for b in all_books:
                if b["id"] == book_id:
                    continue
                p = get_progress(c, b["id"])
                if p and p["rolling_summary"]:
                    other_books.append({"title": b["title"], "summary": p["rolling_summary"]})
            system_prompt = build_synthesis_prompt(
                current_title=book["title"],
                current_summary=rolling_summary,
                other_books=other_books,
            )
            session_id = add_session(c, book_id=book_id, chapter=None, session_type="compare")

        # Build initial message history and get opening question
        messages = [{"role": "system", "content": system_prompt}]
        opening = chat(messages)
        messages.append({"role": "assistant", "content": opening})
        add_exchange(c, session_id=session_id, role="assistant", content=opening, seq=1)

        # Store conversation history in memory for subsequent turns
        active_sessions[session_id] = messages

        return RedirectResponse(url=f"/session/{session_id}", status_code=303)

    return app
