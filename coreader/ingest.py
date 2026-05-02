from pathlib import Path
import ebooklib
from ebooklib import epub
from pypdf import PdfReader
from bs4 import BeautifulSoup


def detect_format(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".epub":
        return "epub"
    if suffix == ".pdf":
        return "pdf"
    raise ValueError(f"Unsupported file format: {suffix}")


def extract_chapters(path: Path) -> list[dict]:
    fmt = detect_format(path)
    if fmt == "epub":
        return _extract_epub(path)
    return _extract_pdf(path)


def _extract_epub(path: Path) -> list[dict]:
    book = epub.read_epub(str(path))
    chapters = []
    number = 1
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text(separator="\n").strip()
        if len(text) < 100:
            continue
        title = (soup.find("h1") or soup.find("h2") or soup.find("title"))
        title_text = title.get_text(strip=True) if title else f"Chapter {number}"
        chapters.append({"number": number, "title": title_text, "text": text})
        number += 1
    return chapters


def _extract_pdf(path: Path) -> list[dict]:
    reader = PdfReader(str(path))
    chapters = []
    chapter_number = 1

    # PDFs without ToC: treat every 20 pages as one chapter
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
