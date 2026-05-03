import tomllib
from pathlib import Path

COREADER_DIR = Path.home() / ".coreader"
CONFIG_PATH = COREADER_DIR / "config.toml"
BOOKS_DIR = COREADER_DIR / "books"
DEFAULT_MODEL = "gemma4:e4b"


def load_model() -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("model", DEFAULT_MODEL)
    return DEFAULT_MODEL


def ensure_dirs():
    COREADER_DIR.mkdir(exist_ok=True)
    BOOKS_DIR.mkdir(exist_ok=True)
