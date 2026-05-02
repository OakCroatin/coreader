from coreader.ollama_client import stream_print
from coreader.db import get_progress, add_session, add_exchange, list_books


def build_synthesis_prompt(
    current_title: str,
    current_summary: str,
    other_books: list[dict]
) -> str:
    if other_books:
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
    progress = get_progress(conn, book_id)
    current_summary = progress["rolling_summary"] if progress else ""

    all_books = list_books(conn)
    other_books = []
    for b in all_books:
        if b["id"] == book_id:
            continue
        p = get_progress(conn, b["id"])
        if p and p["rolling_summary"]:
            other_books.append({"title": b["title"], "summary": p["rolling_summary"]})

    system_prompt = build_synthesis_prompt(
        current_title=book_title,
        current_summary=current_summary,
        other_books=other_books
    )

    session_id = add_session(conn, book_id=book_id, chapter=None, session_type="compare")
    messages = [{"role": "system", "content": system_prompt}]
    seq = 1

    print(f"\n--- Co-Reader: Cross-Book Synthesis for '{book_title}' ---")
    print("(Type your response. Type 'done' to finish.)\n")

    response = stream_print(messages)
    messages.append({"role": "assistant", "content": response})
    add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
    seq += 1

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "done":
            break
        if not user_input:
            continue

        add_exchange(conn, session_id=session_id, role="user", content=user_input, seq=seq)
        seq += 1
        messages.append({"role": "user", "content": user_input})
        response = stream_print(messages)
        messages.append({"role": "assistant", "content": response})
        add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
        seq += 1

    print("\nSession saved.")
