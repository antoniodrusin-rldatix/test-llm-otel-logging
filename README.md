# TetOtel

OpenTelemetry examples and utilities (span logging, LLM logging).

## Setup

Run these commands in **WSL** (Windows Subsystem for Linux).

### Create and use a virtual environment

```bash
# Create venv (if you don't have one yet)
python3 -m venv .venv

# Activate (WSL / Linux)
source .venv/bin/activate
```

Then install dependencies:

```bash
pip install -r requirements.txt
```

## Updating the venv

After changing `requirements.txt` or pulling changes that modify it:

1. **Activate the venv** (if not already active):

   ```bash
   source .venv/bin/activate
   ```

2. **Sync installed packages with requirements** (recommended):

   ```bash
   pip install -r requirements.txt --upgrade
   ```

   This installs any new dependencies and upgrades existing ones to versions allowed by `requirements.txt`.

3. **Optional — upgrade all packages to latest compatible versions:**

   ```bash
   pip install -r requirements.txt --upgrade
   pip list --outdated   # see what’s outdated
   ```

To **recreate the venv from scratch** (e.g. to avoid broken state):

```bash
deactivate
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Files

- `otel_span_log.py` / `otel_span_log_windows.md` — span logging example
- `otel_llm_log.py` / `otel_llm_log.md` — LLM logging example
- `requirements.txt` — Python dependencies
