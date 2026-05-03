import click
from pathlib import Path
from coreader.config import ensure_dirs, BOOKS_DIR
from coreader.db import get_connection, init_db, add_book, add_chapter, get_book_by_title, list_books, get_progress, get_chapter_count, remove_book
from coreader.ingest import extract_chapters
from coreader.session import run_checkin_session
from coreader.synthesizer import run_compare_session


BANNER = r"""
  ____  ___  ____  _____    _    ____  _____  ____
 / ___// _ \|  _ \| ____|  / \  |  _ \| ____||  _ \
| |   | | | | |_) |  _|   / _ \ | | | |  _|  | |_) |
| |___| |_| |  _ <| |___ / ___ \| |_| | |___ |  _ <
 \____|\___/ |_| \_\_____/_/   \_\____/ |_____||_| \_\

           your reading companion
"""


@click.group()
def cli():
    """Co-Reader: your interactive reading companion."""
    ensure_dirs()
    click.echo(BANNER)


@cli.command()
@click.argument("file", type=click.Path(path_type=Path))
def add(file: Path):
    """Ingest an EPUB or PDF book. Drop books in ~/.coreader/books/ and pass the filename."""
    if not file.is_absolute() and not file.exists():
        file = BOOKS_DIR / file
    if not file.exists():
        click.echo(f"File not found: {file}\nDrop your book into ~/.coreader/books/ and try again.")
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
    """Remove a book and all its sessions from the database."""
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found.")
        return

    click.confirm(f"Remove '{title}' and all its sessions? This cannot be undone.", abort=True)
    remove_book(conn, book["id"])
    click.echo(f"Removed '{title}'.")


@cli.command()
@click.argument("title")
@click.argument("chapter", type=int)
def checkin(title: str, chapter: int):
    """Start an interactive dialogue after finishing a chapter."""
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found. Run 'coreader add' first.")
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
    """Run cross-book synthesis dialogue for a book."""
    conn = get_connection()
    init_db(conn)

    book = get_book_by_title(conn, title)
    if not book:
        click.echo(f"Book '{title}' not found.")
        return

    run_compare_session(conn=conn, book_id=book["id"], book_title=book["title"])


@cli.command()
def status():
    """Show all books and reading progress."""
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
