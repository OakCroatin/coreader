import tomllib
from pathlib import Path

CONFIG_PATH = Path.home() / ".coreader" / "config.toml"
DEFAULT_MODEL = "gemma4:e4b"


def load_model() -> str:
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("model", DEFAULT_MODEL)
    return DEFAULT_MODEL
