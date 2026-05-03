"""
config.py — App-wide paths and model configuration.

Loads the Ollama model name from ~/.coreader/config.toml if present,
otherwise falls back to DEFAULT_MODEL. Also defines shared directory
paths used across the app.
"""

import tomllib
from pathlib import Path

# ~/.coreader/ — stores the database and config file
COREADER_DIR = Path.home() / ".coreader"

# Path to the optional user config file
CONFIG_PATH = COREADER_DIR / "config.toml"

# books/ lives inside the project folder so users can find it easily
BOOKS_DIR = Path(__file__).parent.parent / "books"

# Fallback model if no config.toml is present
DEFAULT_MODEL = "gemma4:e4b"


def load_model() -> str:
    """Return the Ollama model name from config.toml, or the default."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("model", DEFAULT_MODEL)
    return DEFAULT_MODEL


def ensure_dirs():
    """Create ~/.coreader/ and the books/ folder if they don't exist yet."""
    COREADER_DIR.mkdir(exist_ok=True)
    BOOKS_DIR.mkdir(exist_ok=True)
