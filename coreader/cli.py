"""
cli.py — Command-line interface for Co-Reader.

Defines five commands:
  add     — ingest an EPUB or PDF from the books/ folder or a full path
  remove  — delete a book and all its sessions from the database
  checkin — start a Socratic dialogue after finishing a chapter
  compare — run a cross-book synthesis session
  status  — display all books and reading progress

The ASCII banner is printed on every command invocation via the cli() group.
"""

import pyfiglet
import click
import uvicorn
from pathlib import Path
from coreader.config import ensure_dirs, BOOKS_DIR, load_model, save_model
from coreader.db import get_connection, init_db, add_book, add_chapter, get_book_by_title, list_books, get_progress, get_chapter_count, remove_book
from coreader.ingest import extract_chapters
from coreader.session import run_checkin_session
from coreader.synthesizer import run_compare_session


def _make_banner() -> str:
    """Combine the book stack art and the COREADER title side by side."""
    book = [
        "               (  ",
        "              ( ) ",
        "     _______   Y  ",
        "    /      /, |\"|",
        "   /      //  | | ",
        "  /______//,  | | ",
        " (______(//   ,-. ",
        "(______(//   ('-')",
        "(______(/     `-' ",
    ]
    # Generate the title using pyfiglet for pixel-perfect letter alignment
    title = pyfiglet.figlet_format("COREADER").rstrip("\n").split("\n")
    gap = " " * 10
    book_width = max(len(l) for l in book)
    title_start = 2  # which book row the title begins on

    lines = [""]
    for i, book_line in enumerate(book):
        ti = i - title_start
        padded = book_line.ljust(book_width)
        if 0 <= ti < len(title):
            lines.append(padded + gap + title[ti])
        else:
            lines.append(padded)
    lines.append("")
    lines.append(" " * (book_width + len(gap)) + "your reading companion")
    lines.append("")
    return "\n".join(lines)


BANNER = _make_banner()


@click.group()
def cli():
    """Co-Reader: your interactive reading companion."""
    ensure_dirs()
    click.echo(BANNER)


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
def add(file: Path):
    """Ingest an EPUB or PDF book.

    Drop the file into the books/ folder inside the project, then pass just
    the filename. Or pass a full path to any file on your system.

    \b
    Examples:
      coreader add mybook.epub
      coreader add /home/user/downloads/mybook.pdf
    """
    if not file.is_absolute() and not file.exists():
        file = BOOKS_DIR / file
    if not file.exists():
        click.echo(f"File not found: {file}\nDrop your book into {BOOKS_DIR}/ and try again.")
        return
    conn = get_connection()
    init_db(conn)

    click.echo(f"Parsing {file.name}...")
    chapters = extract_chapters(file)
    click.echo(f"Found {len(chapters)} chapters.")

    title = click.prompt("Book title")
    author = click.prompt("Author", default="Unknown")
    book_type = click.prompt("Type", type=click.Choice(["fiction", "nonfiction"]))

    existing = get_book_by_title(conn, title)
    if existing:
        click.echo(f"Book '{title}' already exists. Skipping.")
        return

    book_id = add_book(conn, title=title, author=author, book_type=book_type, file_path=str(file))
    for ch in chapters:
        add_chapter(conn, book_id=book_id, number=ch["number"], title=ch["title"], text=ch["text"])

    click.echo(f"Added '{title}' with {len(chapters)} chapters.")


@cli.command()
@click.argument("title")
def remove(title: str):
    """Remove a book and all its sessions from the database.

    Deletes the book, all chapters, progress, and session history.
    You will be asked to confirm before anything is deleted.

    \b
    Example:
      coreader remove "No Nonsense Spirituality"
    """
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found.")
        books = list_books(conn)
        if books:
            click.echo("Available books:")
            for b in books:
                click.echo(f"  {b['title']}")
        return

    click.confirm(f"Remove '{title}' and all its sessions? This cannot be undone.", abort=True)
    remove_book(conn, book["id"])
    click.echo(f"Removed '{title}'.")


@cli.command()
@click.argument("title")
@click.argument("chapter", type=int)
def checkin(title: str, chapter: int):
    """Start an interactive Socratic dialogue after finishing a chapter.

    Ask evaluative questions about the chapter. Type 'done' to end the session.
    The rolling summary updates automatically when you finish.

    \b
    Example:
      coreader checkin "No Nonsense Spirituality" 7
    """
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found.")
        books = list_books(conn)
        if books:
            click.echo("Available books:")
            for b in books:
                click.echo(f"  {b['title']}")
        else:
            click.echo("No books added yet. Run 'coreader add' first.")
        return

    run_checkin_session(
        conn=conn,
        book_id=book["id"],
        chapter_number=chapter,
        book_title=book["title"],
        book_type=book["type"]
    )


@cli.command()
@click.argument("title")
def compare(title: str):
    """Surface connections between a book and everything else you've read.

    \b
    Example:
      coreader compare "No Nonsense Spirituality"
    """
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found.")
        books = list_books(conn)
        if books:
            click.echo("Available books:")
            for b in books:
                click.echo(f"  {b['title']}")
        return

    run_compare_session(conn=conn, book_id=book["id"], book_title=book["title"])


@cli.command()
def model():
    """Show available Ollama models and switch the active one.

    Lists all models installed on this machine. Select a number to switch,
    or press Enter to keep the current model.

    \b
    Example:
      coreader model
    """
    import ollama as _ollama
    try:
        models = [m.model for m in _ollama.list().models]
    except Exception:
        click.echo("Could not reach Ollama. Make sure it is running.")
        return

    if not models:
        click.echo("No models found. Run 'ollama pull <model>' to install one.")
        return

    current = load_model()
    click.echo(f"\nCurrent model: {current}\n")
    click.echo("Available models:")
    for i, m in enumerate(models, 1):
        marker = " <-- active" if m == current else ""
        click.echo(f"  [{i}] {m}{marker}")

    click.echo()
    choice = click.prompt("Select a model number (Enter to keep current)", default="", show_default=False)

    if not choice.strip():
        click.echo("No change.")
        return

    if not choice.isdigit() or not (1 <= int(choice) <= len(models)):
        click.echo("Invalid selection.")
        return

    selected = models[int(choice) - 1]
    save_model(selected)
    click.echo(f"Model set to '{selected}'.")


@cli.command()
@click.option("--port", default=8000, show_default=True, help="Port to listen on.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to.")
def serve(port: int, host: str):
    """Launch the Co-Reader web UI in your browser.

    \b
    Example:
      coreader serve
      coreader serve --port 9000
    """
    click.echo(f"Starting Co-Reader web UI at http://{host}:{port}")
    click.echo("Press Ctrl+C to stop.\n")
    uvicorn.run("coreader.web:app", host=host, port=port, reload=False)


@cli.command()
def status():
    """Show all books, chapter progress, and last check-in date."""
    conn = get_connection()
    init_db(conn)

    books = list_books(conn)
    if not books:
        click.echo("No books added yet. Use 'coreader add <file>'.")
        return

    click.echo(f"\n{'Title':<35} {'Type':<12} {'Progress':<15} {'Last Check-in'}")
    click.echo("-" * 80)
    for book in books:
        progress = get_progress(conn, book["id"])
        total = get_chapter_count(conn, book["id"])
        last_ch = progress["last_chapter"] if progress else 0
        updated = progress["updated_at"][:10] if progress and progress["updated_at"] else "—"
        click.echo(f"{book['title']:<35} {book['type']:<12} {last_ch}/{total} chapters    {updated}")
    click.echo()
