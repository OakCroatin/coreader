import click
from pathlib import Path
from coreader.db import get_connection, init_db, add_book, add_chapter, get_book_by_title
from coreader.ingest import extract_chapters


@click.group()
def cli():
    """Co-Reader: your interactive reading companion."""
    pass


@cli.command()
@click.argument("file", type=click.Path(exists=True, path_type=Path))
def add(file: Path):
    """Ingest an EPUB or PDF book."""
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
