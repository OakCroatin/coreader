import pytest
from unittest.mock import patch, MagicMock
from coreader.session import build_checkin_prompt, build_summary_update_prompt


def test_checkin_prompt_fiction_includes_chapter_text():
    prompt = build_checkin_prompt(
        book_type="fiction",
        title="Dune",
        chapter_number=3,
        chapter_text="Paul walked into the desert.",
        rolling_summary="Paul arrived on Arrakis."
    )
    assert "Paul walked into the desert." in prompt
    assert "Paul arrived on Arrakis." in prompt
    assert "character" in prompt.lower() or "arc" in prompt.lower()


def test_checkin_prompt_nonfiction_focuses_on_arguments():
    prompt = build_checkin_prompt(
        book_type="nonfiction",
        title="Sapiens",
        chapter_number=2,
        chapter_text="Humans developed agriculture.",
        rolling_summary="Cognitive revolution happened."
    )
    assert "Humans developed agriculture." in prompt
    assert "argument" in prompt.lower() or "framework" in prompt.lower()


def test_summary_update_prompt_includes_all_inputs():
    prompt = build_summary_update_prompt(
        title="Sapiens",
        chapter_number=2,
        chapter_text="Agriculture chapter.",
        rolling_summary="Old summary.",
        dialogue_text="User said: interesting."
    )
    assert "Agriculture chapter." in prompt
    assert "Old summary." in prompt
    assert "User said: interesting." in prompt
