from typing import Generator
import ollama
from coreader.config import load_model


def chat(messages: list[dict], stream: bool = False) -> str | Generator:
    """Send a message list to Ollama. Returns full response string or a stream generator."""
    model = load_model()
    if stream:
        return ollama.chat(model=model, messages=messages, stream=True)
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


def stream_print(messages: list[dict]) -> str:
    """Stream response to stdout, return full content string."""
    model = load_model()
    full = []
    for chunk in ollama.chat(model=model, messages=messages, stream=True):
        piece = chunk["message"]["content"]
        print(piece, end="", flush=True)
        full.append(piece)
    print()
    return "".join(full)
