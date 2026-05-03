"""
ollama_client.py — Thin wrapper around the Ollama Python SDK.

All LLM calls in the app go through these two functions so that
model loading and streaming logic stay in one place.
"""

from typing import Generator
import ollama
from coreader.config import load_model


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
    """Stream the model response to stdout in real time and return the full text.

    Prints each token as it arrives (no buffering), then returns the
    complete response string so it can be stored in the database.

    Args:
        messages: List of role/content dicts to send to the model.

    Returns:
        The complete response as a single string.
    """
    model = load_model()
    full = []
    for chunk in ollama.chat(model=model, messages=messages, stream=True):
        piece = chunk["message"]["content"]
        print(piece, end="", flush=True)  # print token immediately
        full.append(piece)
    print()  # newline after stream ends
    return "".join(full)
