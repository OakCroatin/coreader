# Transferring coreader to Another Machine

## What transfers

- The app code (this repo)
- Your reading history, sessions, and rolling summaries (`~/.coreader/coreader.db`) — optional

## Step 1: Copy the project

**Option A — USB drive or direct copy**
```bash
# On the source machine:
cp -r ~/Projects/coreader /path/to/usb/coreader

# On the target machine:
cp -r /path/to/usb/coreader ~/Projects/coreader
```

**Option B — Over the network (SCP)**
```bash
scp -r ~/Projects/coreader user@targetmachine:~/Projects/coreader
```

**Option C — GitHub (if you push the repo)**
```bash
# On the target machine:
git clone https://github.com/yourusername/coreader ~/Projects/coreader
```

## Step 2: Install on the target machine

Requires Python 3.11+. Check with `python3 --version`.

```bash
cd ~/Projects/coreader
python3 -m venv .venv
source .venv/bin/activate    # Linux/Mac
# or: .venv\Scripts\activate  # Windows
pip install -e .
```

## Step 3: Install and start Ollama

If Ollama isn't on the target machine:

```bash
# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Then pull your model
ollama pull gemma3:27b
```

Check available models after pulling:
```bash
ollama list
```

## Step 4: Set the model for this machine

Create `~/.coreader/config.toml` on the target machine with the exact model name shown by `ollama list`:

```toml
model = "gemma3:27b"
```

Each machine can have its own `config.toml` pointing to whatever model is available locally. The app code is the same on all machines.

## Step 5 (optional): Transfer your reading history

If you want your sessions, rolling summaries, and progress to carry over:

```bash
# Create the directory on the target machine first
mkdir -p ~/.coreader

# Copy the database
scp ~/.coreader/coreader.db user@targetmachine:~/.coreader/coreader.db
```

If you skip this step, you start fresh on the new machine. You can always re-add books with `coreader add` — only the session history and rolling summaries won't carry over.

## Verify the transfer

```bash
source ~/Projects/coreader/.venv/bin/activate
coreader --help       # should show all 4 commands
coreader status       # shows your books if you transferred the DB
```

## Notes

- The virtualenv (`.venv/`) does not transfer — always recreate it with `python3 -m venv .venv && pip install -e .`
- The database (`~/.coreader/coreader.db`) lives outside the project folder and does NOT get included in a git push — transfer it separately if needed
- Book files (EPUB/PDF) are not stored in the database, only the extracted chapter text — you don't need to transfer the original files
