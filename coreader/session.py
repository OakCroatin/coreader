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
    chapter = get_chapter(conn, book_id=book_id, number=chapter_number)
    if not chapter:
        print(f"Chapter {chapter_number} not found for '{book_title}'.")
        return

    progress = get_progress(conn, book_id)
    rolling_summary = progress["rolling_summary"] if progress else ""

    system_prompt = build_checkin_prompt(
        book_type=book_type,
        title=book_title,
        chapter_number=chapter_number,
        chapter_text=chapter["text"],
        rolling_summary=rolling_summary
    )

    session_id = add_session(conn, book_id=book_id, chapter=chapter_number, session_type="checkin")
    messages = [{"role": "system", "content": system_prompt}]
    exchanges = []
    seq = 1

    print(f"\n--- Co-Reader: {book_title}, Chapter {chapter_number} ---")
    print("(Type your response after each question. Type 'done' to finish.)\n")

    # Get opening question
    response = stream_print(messages)
    messages.append({"role": "assistant", "content": response})
    add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
    exchanges.append(f"Assistant: {response}")
    seq += 1

    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == "done":
            break
        if not user_input:
            continue

        add_exchange(conn, session_id=session_id, role="user", content=user_input, seq=seq)
        exchanges.append(f"User: {user_input}")
        seq += 1

        messages.append({"role": "user", "content": user_input})
        response = stream_print(messages)
        messages.append({"role": "assistant", "content": response})
        add_exchange(conn, session_id=session_id, role="assistant", content=response, seq=seq)
        exchanges.append(f"Assistant: {response}")
        seq += 1

    # Update rolling summary
    print("\n(Updating reading summary...)")
    dialogue_text = "\n".join(exchanges)
    summary_prompt = build_summary_update_prompt(
        title=book_title,
        chapter_number=chapter_number,
        chapter_text=chapter["text"],
        rolling_summary=rolling_summary,
        dialogue_text=dialogue_text
    )
    new_summary = chat([{"role": "user", "content": summary_prompt}])
    update_progress(conn, book_id=book_id, last_chapter=chapter_number, rolling_summary=new_summary)
    print("Summary updated. See you next chapter.")
