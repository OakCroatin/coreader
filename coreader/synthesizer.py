"""
synthesizer.py — Cross-book synthesis session logic.

A compare session surfaces connections between the current book and
everything else the user has read. It works by:
  1. Loading the rolling summaries of all other books in the database
  2. Building a prompt that asks the LLM to find non-obvious links
  3. Running an open-ended dialogue loop (no summary update at the end)

Unlike checkin sessions, compare sessions don't update any progress data —
they're purely exploratory.
"""

from coreader.ollama_client import stream_print
from coreader.db import get_progress, add_session, add_exchange, list_books


def build_synthesis_prompt(
    current_title: str,
    current_summary: str,
    other_books: list[dict]
) -> str:
    """Build the system prompt for a cross-book synthesis session.

    Passes the current book's rolling summary and summaries of all other
    books to the LLM so it can find meaningful connections.

    Args:
        current_title:   Title of the book the user is currently reading
        current_summary: Rolling summary of the current book so far
        other_books:     List of dicts with 'title' and 'summary' for other books

    Returns:
        A system prompt string ready to pass to the LLM.
    """
    if other_books:
        # Format each other book as a labeled block
        books_section = "\n\n".join(
            f"**{b['title']}**\n{b['summary']}" for b in other_books
        )
    else:
        books_section = "(No other completed books yet.)"

    return f"""You are helping a reader find meaningful connections across their reading history.

CURRENT BOOK — "{current_title}" (reading in progress):
{current_summary if current_summary else "(no summary yet — book just started)"}

OTHER BOOKS READ:
{books_section}

Surface 2-3 specific, non-obvious connections: overlapping frameworks, contradicting arguments, parallel character arcs, or authors who would push back on each other.
Present one connection at a time and invite the reader to respond."""


def run_compare_session(conn, book_id: int, book_title: str) -> None:
    """Run an interactive cross-book synthesis session.

    Loads the rolling summaries of all books in the database (excluding the
    current one), then enters a dialogue loop. No progress data is updated
    at the end — sessions are saved for history only.

    Args:
        conn:       Active database connection
        book_id:    ID of the book being used as the focal point
        book_title: Display name of the focal book
    """
    # Load the current book's rolling summary
    progress = get_progress(conn, book_id)
    current_summary = progress["rolling_summary"] if progress else ""

    # Gather summaries from all other books that have been read
    all_books = list_books(conn)
    other_books = []
    for b in all_books:
        if b["id"] == book_id:
            continue  # skip the current book
        p = get_progress(conn, b["id"])
        # Only include books that have a non-empty rolling summary
        if p and p["rolling_summary"]:
            other_books.append({"title": b["title"], "summary": p["rolling_summary"]})

    # Build the system prompt and create a session record
    system_prompt = build_synthesis_prompt(
        current_title=book_title,
        current_summary=current_summary,
        other_books=other_books
    )
    session_id = add_session(conn, book_id=book_id, chapter=None, session_type="compare")

    # messages holds the full conversation history for the LLM
    messages = [{"role": "system", "content": system_prompt}]
    seq = 1  # sequence counter for ordering exchanges in the database

    print(f"\n--- Co-Reader: Cross-Book Synthesis for '{book_title}' ---")
    print("(Type your response. Type 'done' to finish.)\n")

    # Get the opening synthesis observation from the LLM
    response = stream_print(messages)
    messages.append({"role": "assistant", "content": response})
    add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
    seq += 1

    # Dialogue loop — continues until user types 'done'
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "done":
            break
        if not user_input:
            continue

        # Save user turn and send updated history to LLM
        add_exchange(conn, session_id=session_id, role="user", content=user_input, seq=seq)
        seq += 1
        messages.append({"role": "user", "content": user_input})
        response = stream_print(messages)
        messages.append({"role": "assistant", "content": response})
        add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
        seq += 1

    print("\nSession saved.")
