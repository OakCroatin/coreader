# Running coreader

## First-time setup

```bash
cd ~/Projects/coreader
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Every session

Activate the virtualenv before using any `coreader` command:

```bash
source ~/Projects/coreader/.venv/bin/activate
```

You can add this alias to your `~/.zshrc` or `~/.bashrc` so you don't have to think about it:

```bash
alias coreader='source ~/Projects/coreader/.venv/bin/activate && coreader'
```

## Ollama must be running

```bash
ollama serve
```

Or check if it's already running:

```bash
ollama list
```

If you see your model listed, it's running. If not, start it with `ollama serve` in a separate terminal.

## Daily workflow

### Add a new book (once per book)

Drop the EPUB or PDF into the `books/` folder inside the project (`~/Projects/coreader/books/`), then:

```bash
coreader add "my-book.epub"
```

You can also pass a full path if you prefer:

```bash
coreader add /path/to/book.epub
```

You'll be prompted for title, author, and type (fiction or nonfiction).

### Check in after finishing a chapter
```bash
coreader checkin "Book Title" 7
```
Starts a Socratic dialogue. The app asks evaluative questions about the chapter.
Type your responses. Type `done` to end the session.
The rolling summary updates automatically when you're done.

### Cross-book synthesis (any time)
```bash
coreader compare "Book Title"
```
Surfaces connections between the current book and everything else you've read.
Type `done` to end the session.

### View your progress
```bash
coreader status
```

## Web UI

Start the browser-based interface with:

```bash
coreader serve
```

Then open `http://localhost:8000` in your browser.

Options:
```bash
coreader serve --port 9000         # use a different port
coreader serve --host 0.0.0.0      # bind to all interfaces
```

The web UI lets you browse your library, start checkin and compare sessions, and chat with the AI — all from the browser. The CLI commands continue to work normally alongside it.

> Note: Ollama must be running (`ollama serve`) for sessions to work.

---

## Configuration

To use a different Ollama model, create `~/.coreader/config.toml`:

```toml
model = "mistral"
```

The default model is whatever is set in `coreader/config.py` (currently `gemma4:e4b`).

## Your data

All sessions, summaries, and reading history live in:

```
~/.coreader/coreader.db
```

This is a standard SQLite database. You can inspect it with any SQLite browser.
