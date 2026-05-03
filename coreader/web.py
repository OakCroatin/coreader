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
            try:
                chapter_num = int(chapter)
            except ValueError:
                return HTMLResponse("Invalid chapter number", status_code=400)
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

    @app.get("/session/{session_id}", response_class=HTMLResponse)
    async def chat_view(request: Request, session_id: int):
        """Chat page — loads existing exchanges and renders the chat UI."""
        c = get_conn()
        exchanges = get_exchanges(c, session_id)
        session_row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not session_row:
            return HTMLResponse("Session not found", status_code=404)
        books = list_books(c)
        book = next((b for b in books if b["id"] == session_row["book_id"]), None)
        return templates.TemplateResponse(request, "chat.html", {
            "session_id": session_id,
            "session_type": session_row["type"],
            "chapter": session_row["chapter"],
            "book": book,
            "exchanges": [{"role": e["role"], "content": e["content"]} for e in exchanges],
        })

    @app.post("/session/{session_id}/message")
    async def send_message(session_id: int, request: Request):
        """Receive a user message, call Ollama, return assistant response as JSON."""
        body = await request.json()
        user_content = body.get("content", "").strip()
        if not user_content:
            return JSONResponse({"error": "empty message"}, status_code=400)

        c = get_conn()
        messages = active_sessions.get(session_id)
        if messages is None:
            # Reconstruct from DB if server was restarted
            session_row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
            if not session_row:
                return JSONResponse({"error": "session not found"}, status_code=404)
            exchanges = get_exchanges(c, session_id)
            messages = [{"role": e["role"], "content": e["content"]} for e in exchanges]
            active_sessions[session_id] = messages

        # Determine next seq number
        seq = c.execute("SELECT COUNT(*) FROM exchanges WHERE session_id=?", (session_id,)).fetchone()[0] + 1

        # Save and append user turn
        add_exchange(c, session_id=session_id, role="user", content=user_content, seq=seq)
        messages.append({"role": "user", "content": user_content})
        seq += 1

        # Call Ollama (buffered)
        response_text = chat(messages)

        # Save and append assistant turn
        add_exchange(c, session_id=session_id, role="assistant", content=response_text, seq=seq)
        messages.append({"role": "assistant", "content": response_text})

        return JSONResponse({"role": "assistant", "content": response_text})

    @app.post("/session/{session_id}/done")
    async def end_session(session_id: int):
        """End a session. For checkins, generates and saves a rolling summary update."""
        c = get_conn()
        session_row = c.execute("SELECT * FROM sessions WHERE id=?", (session_id,)).fetchone()
        if not session_row:
            return JSONResponse({"error": "session not found"}, status_code=404)

        if session_row["type"] == "checkin":
            # Build the summary update from stored exchanges
            exchanges = get_exchanges(c, session_id)
            dialogue_text = "\n".join(
                f"{'Assistant' if e['role'] == 'assistant' else 'User'}: {e['content']}"
                for e in exchanges
            )
            book_id = session_row["book_id"]
            chapter_num = session_row["chapter"]
            ch = get_chapter(c, book_id, chapter_num)
            progress = get_progress(c, book_id)
            rolling_summary = progress["rolling_summary"] if progress else ""
            books = list_books(c)
            book = next((b for b in books if b["id"] == book_id), None)

            summary_prompt = build_summary_update_prompt(
                title=book["title"],
                chapter_number=chapter_num,
                chapter_text=ch["text"] if ch else "",
                rolling_summary=rolling_summary,
                dialogue_text=dialogue_text,
            )
            new_summary = chat([{"role": "user", "content": summary_prompt}])
            update_progress(c, book_id=book_id, last_chapter=chapter_num, rolling_summary=new_summary)

        # Clear in-memory session state
        active_sessions.pop(session_id, None)
        return JSONResponse({"status": "ok"})

    @app.delete("/books/{book_id}")
    async def delete_book(book_id: int):
        """Remove a book and all its data from the database."""
        c = get_conn()
        remove_book(c, book_id)
        return JSONResponse({"status": "ok"})

    return app
