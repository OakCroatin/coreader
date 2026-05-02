import pytest
from pathlib import Path
from coreader.ingest import extract_chapters, detect_format

SAMPLE_DIR = Path(__file__).parent.parent / "sample_books"

def test_detect_epub_format():
    assert detect_format(SAMPLE_DIR / "test.epub") == "epub"

def test_extract_chapters_returns_list():
    chapters = extract_chapters(SAMPLE_DIR / "test.epub")
    assert isinstance(chapters, list)
    assert len(chapters) >= 1

def test_chapter_has_required_keys():
    chapters = extract_chapters(SAMPLE_DIR / "test.epub")
    ch = chapters[0]
    assert "number" in ch
    assert "title" in ch
    assert "text" in ch
    assert isinstance(ch["text"], str)
    assert len(ch["text"]) > 0

def test_chapter_numbers_are_sequential():
    chapters = extract_chapters(SAMPLE_DIR / "test.epub")
    for i, ch in enumerate(chapters, start=1):
        assert ch["number"] == i
