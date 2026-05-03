"""
session.py — Checkin session logic (chapter dialogue + rolling summary update).

A checkin session works in three phases:
  1. Build a system prompt with the chapter text and prior rolling summary
  2. Run an interactive Socratic dialogue loop with the user
  3. After 'done', send the full dialogue to the LLM to update the rolling summary

The rolling summary is a dense, cumulative record of what's been read so far.
It gets passed into every new checkin so the LLM has context across chapters.
"""

from coreader.ollama_client import stream_print, chat
from coreader.db import (
    get_chapter, get_progress, update_progress,
    add_session, add_exchange, get_exchanges
)


def build_checkin_prompt(
    book_type: str,
    title: str,
    chapter_number: int,
    chapter_text: str,
    rolling_summary: str
) -> str:
    """Build the system prompt for a checkin session.

    The prompt changes based on book type:
      - fiction:    focuses on character, motivation, narrative tension
      - nonfiction: focuses on arguments, frameworks, cross-chapter connections

    Args:
        book_type:       'fiction' or 'nonfiction'
        title:           Book title shown in the prompt
        chapter_number:  Which chapter was just finished
        chapter_text:    Full text of that chapter
        rolling_summary: Accumulated summary of all prior chapters

    Returns:
        A system prompt string ready to pass to the LLM.
    """
    if book_type == "fiction":
        focus = (
            "character arc and motivation, how characters have changed, "
            "relationships, foreshadowing, narrative tension"
        )
        style = "evaluative questions about character and story development"
    else:
        focus = (
            "key arguments, recurring patterns, how this chapter connects to or "
            "complicates earlier ones, frameworks worth remembering"
        )
        style = "questions connecting ideas across chapters and challenging assumptions"

    return f"""You are a thoughtful reading companion. The user has just finished chapter {chapter_number} of "{title}".

ROLLING SUMMARY (chapters so far):
{rolling_summary if rolling_summary else "(no prior chapters)"}

CHAPTER {chapter_number} TEXT:
{chapter_text}

Your role: engage the user in a Socratic dialogue about this chapter.
Focus on: {focus}.
Ask one {style} at a time. When the user responds, go deeper or challenge their interpretation.
Do not summarize — provoke thinking. Begin with your first question."""


def build_summary_update_prompt(
    title: str,
    chapter_number: int,
    chapter_text: str,
    rolling_summary: str,
    dialogue_text: str
) -> str:
    """Build the prompt used to update the rolling summary after a session.

    Instructs the LLM to incorporate the chapter content and the dialogue
    insights into an updated cumulative summary (max 800 words).

    Args:
        title:           Book title
        chapter_number:  Chapter that was just discussed
        chapter_text:    Raw chapter text
        rolling_summary: The existing summary before this chapter
        dialogue_text:   The full checkin dialogue as a single string

    Returns:
        A user-role prompt string for the summary update call.
    """
    return f"""Update the rolling reading summary for "{title}" after chapter {chapter_number}.

Incorporate:
1. What happened or was argued in chapter {chapter_number}
2. Key insights or patterns noted in the dialogue
3. Character or thematic developments worth tracking

CURRENT ROLLING SUMMARY:
{rolling_summary if rolling_summary else "(none yet)"}

CHAPTER {chapter_number} TEXT:
{chapter_text}

DIALOGUE:
{dialogue_text}

Write an updated rolling summary. Be dense and specific. Keep it under 800 words."""


def run_checkin_session(conn, book_id: int, chapter_number: int, book_title: str, book_type: str) -> None:
    """Run an interactive checkin session for a single chapter.

    Loads the chapter text and current rolling summary from the database,
    then enters a dialogue loop. When the user types 'done', the full
    conversation is sent back to the LLM to update the rolling summary.

    Args:
        conn:           Active database connection
        book_id:        ID of the book being checked in
        chapter_number: Chapter the user just finished
        book_title:     Display name of the book
        book_type:      'fiction' or 'nonfiction' — shapes the prompt style
    """
    # Load the chapter text from the database
    chapter = get_chapter(conn, book_id=book_id, number=chapter_number)
    if not chapter:
        print(f"Chapter {chapter_number} not found for '{book_title}'.")
        return

    # Load the rolling summary built from all prior chapters
    progress = get_progress(conn, book_id)
    rolling_summary = progress["rolling_summary"] if progress else ""

    # Build the system prompt and create a session record in the database
    system_prompt = build_checkin_prompt(
        book_type=book_type,
        title=book_title,
        chapter_number=chapter_number,
        chapter_text=chapter["text"],
        rolling_summary=rolling_summary
    )
    session_id = add_session(conn, book_id=book_id, chapter=chapter_number, session_type="checkin")

    # messages is the full conversation history sent to the LLM each turn
    messages = [{"role": "system", "content": system_prompt}]
    exchanges = []  # plain-text copy used later to build the summary prompt
    seq = 1         # sequence counter for ordering exchanges in the database

    print(f"\n--- Co-Reader: {book_title}, Chapter {chapter_number} ---")
    print("(Type your response after each question. Type 'done' to finish.)\n")

    # Get the opening question from the LLM
    response = stream_print(messages)
    messages.append({"role": "assistant", "content": response})
    add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
    exchanges.append(f"Assistant: {response}")
    seq += 1

    # Dialogue loop — continues until user types 'done'
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "done":
            break
        if not user_input:
            continue

        # Save user turn to database and append to history
        add_exchange(conn, session_id=session_id, role="user", content=user_input, seq=seq)
        exchanges.append(f"User: {user_input}")
        seq += 1

        # Send updated history to LLM and stream the response
        messages.append({"role": "user", "content": user_input})
        response = stream_print(messages)
        messages.append({"role": "assistant", "content": response})
        add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
        exchanges.append(f"Assistant: {response}")
        seq += 1

    # After dialogue ends, update the rolling summary
    print("\n(Updating reading summary...)")
    dialogue_text = "\n".join(exchanges)
    summary_prompt = build_summary_update_prompt(
        title=book_title,
        chapter_number=chapter_number,
        chapter_text=chapter["text"],
        rolling_summary=rolling_summary,
        dialogue_text=dialogue_text
    )
    # Use a non-streaming call here — we just need the text, not real-time output
    new_summary = chat([{"role": "user", "content": summary_prompt}])
    update_progress(conn, book_id=book_id, last_chapter=chapter_number, rolling_summary=new_summary)
    print("Summary updated. See you next chapter.")
