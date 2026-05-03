"""
ingest.py — Book parsing for EPUB and PDF files.

Extracts chapters from a book file and returns them as a list of dicts
with 'number', 'title', and 'text' keys. This is the only file that
touches the raw book content — everything else works from the database.
"""

from pathlib import Path
import ebooklib
from ebooklib import epub
from pypdf import PdfReader
from bs4 import BeautifulSoup


def detect_format(path: Path) -> str:
    """Return 'epub' or 'pdf' based on file extension.

    Raises ValueError if the format is not supported.
    """
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return "epub"
    if suffix == ".pdf":
        return "pdf"
    raise ValueError(f"Unsupported file format: {suffix}")


def extract_chapters(path: Path) -> list[dict]:
    """Parse a book file and return a list of chapter dicts.

    Each dict has:
        number (int)  — chapter index starting at 1
        title  (str)  — chapter heading, or 'Chapter N' if none found
        text   (str)  — plain text content of the chapter

    Dispatches to _extract_epub or _extract_pdf based on file type.
    """
    fmt = detect_format(path)
    if fmt == "epub":
        return _extract_epub(path)
    return _extract_pdf(path)


def _extract_epub(path: Path) -> list[dict]:
    """Extract chapters from an EPUB file.

    Iterates over all HTML document items in the EPUB spine. Skips items
    with fewer than 100 characters (covers, ToC pages, etc.). Uses the
    first <h1>, <h2>, or <title> tag as the chapter title.
    """
    book = epub.read_epub(str(path))
    chapters = []
    number = 1

    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        # Parse the HTML content of each spine item
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()

        # Skip very short items — likely front matter, ToC, or blank pages
        if len(text) < 100:
            continue

        # Try to pull a title from common heading tags
        title = (soup.find("h1") or soup.find("h2") or soup.find("title"))
        title_text = title.get_text(strip=True) if title else f"Chapter {number}"

        chapters.append({"number": number, "title": title_text, "text": text})
        number += 1

    return chapters


def _extract_pdf(path: Path) -> list[dict]:
    """Extract chapters from a PDF file.

    PDFs rarely have accessible chapter structure, so we chunk the pages
    into groups of 20 and treat each group as one 'chapter'. This keeps
    individual chunks at a manageable size for the LLM context window.
    """
    reader = PdfReader(str(path))
    chapters = []
    chapter_number = 1

    # Group pages into fixed-size chunks (20 pages each)
    chunk_size = 20
    pages = [p.extract_text() or "" for p in reader.pages]

    for i in range(0, len(pages), chunk_size):
        chunk = "\n".join(pages[i:i + chunk_size]).strip()
        if chunk:
            chapters.append({
                "number": chapter_number,
                "title": f"Section {chapter_number}",
                "text": chunk
            })
            chapter_number += 1

    return chapters
