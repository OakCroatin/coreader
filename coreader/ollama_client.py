"""
ollama_client.py — Thin wrapper around the Ollama Python SDK.

All LLM calls in the app go through these two functions so that
model loading and streaming logic stay in one place.
"""

import textwrap
from typing import Generator
import ollama
from coreader.config import load_model

# Max line width and left indent for all LLM responses
WRAP_WIDTH = 80
INDENT = "  "


def chat(messages: list[dict], stream: bool = False) -> str | Generator:
    """Send a message list to Ollama and return the response.

    Args:
        messages: List of role/content dicts (OpenAI-style message format).
        stream:   If True, returns a raw generator instead of a string.
                  Used when the caller wants to handle streaming itself.

    Returns:
        Full response string (default), or a streaming generator.
    """
    model = load_model()
    if stream:
        return ollama.chat(model=model, messages=messages, stream=True)
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


def stream_print(messages: list[dict]) -> str:
    """Buffer the full model response, then print it wrapped with margins.

    Collects all tokens silently, then word-wraps the complete response
    to WRAP_WIDTH characters with a left indent for readability. Returns
    the original unwrapped text for storage in the database.

    Args:
        messages: List of role/content dicts to send to the model.

    Returns:
        The complete response as a single string (unwrapped, for the DB).
    """
    model = load_model()
    full = []

    # Collect all tokens silently
    for chunk in ollama.chat(model=model, messages=messages, stream=True):
        full.append(chunk["message"]["content"])

    text = "".join(full)

    # Wrap each paragraph separately to preserve intentional line breaks
    paragraphs = text.split("\n")
    wrapped = "\n".join(
        textwrap.fill(p, width=WRAP_WIDTH, initial_indent=INDENT, subsequent_indent=INDENT)
        if p.strip() else ""
        for p in paragraphs
    )
    print(f"\n{wrapped}\n")

    return text
