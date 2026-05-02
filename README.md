# coreader

An interactive reading companion. Check in after each chapter for Socratic dialogue, and compare across your reading history.

Runs entirely locally via Ollama — no API keys, no cloud.

## Requirements

- Python 3.11+
- [Ollama](https://ollama.com) running locally with a model pulled (e.g. `ollama pull llama3`)

## Setup

```bash
git clone <repo>
cd coreader
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Usage

### Add a book

```bash
coreader add mybook.epub
```

Parses the EPUB or PDF and prompts for title, author, and type (fiction or nonfiction).

### Check in after a chapter

```bash
coreader checkin "Book Title" 7
```

Starts an interactive Socratic dialogue about chapter 7. The app asks evaluative questions — for fiction: character arc and motivation; for nonfiction: key arguments and patterns. Type your responses. Type `done` to end the session.

After the session, the rolling summary is updated automatically.

### Cross-book synthesis

```bash
coreader compare "Book Title"
```

Pulls summaries from all your books and asks Ollama to surface non-obvious connections: overlapping frameworks, contradicting arguments, parallel character arcs.

### View progress

```bash
coreader status
```

Shows all books, their type, chapters read, and last check-in date.

## Configuration

Create `~/.coreader/config.toml` to set a custom model:

```toml
model = "mistral"
```

Default model: `gemma4:e4b` (or whatever is set in `coreader/config.py`).

## State

All data lives in `~/.coreader/coreader.db` (SQLite). Safe to inspect with any SQLite browser. Delete to start fresh.

## Project structure

```
coreader/
├── cli.py           # CLI commands (thin wrappers)
├── db.py            # SQLite schema and queries
├── ingest.py        # EPUB/PDF parsing
├── ollama_client.py # Ollama API wrapper
├── session.py       # Dialogue loop and rolling summary
└── synthesizer.py   # Cross-book synthesis
```
