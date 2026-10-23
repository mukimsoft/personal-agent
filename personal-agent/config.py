"""Central configuration. Values come from environment variables (.env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("AGENT_MODEL", "claude-sonnet-5-5")
MAX_TOKENS = int(os.getenv("AGENT_MAX_TOKENS", "4096"))
MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "25"))  # hard cap on tool-loop iterations

# The agent may only read/write inside this directory.
WORKSPACE = Path(os.getenv("AGENT_WORKSPACE", "./workspace")).resolve()
WORKSPACE.mkdir(parents=True, exist_ok=True)

# Where memory and audit logs live.
DATA_DIR = Path(os.getenv("AGENT_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
MEMORY_FILE = DATA_DIR / "memory.json"
AUDIT_LOG = DATA_DIR / "audit.log"

# Email (IMAP read, SMTP send). Use an app password, never your main password.
IMAP_HOST = os.getenv("IMAP_HOST", "imap.gmail.com")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
EMAIL_USER = os.getenv("EMAIL_USER", "")
EMAIL_PASS = os.getenv("EMAIL_PASS", "")

# Approval policy.
# "ask"  -> prompt in terminal before risky tools (interactive use)
# "auto" -> run risky tools without asking (unattended; allowlists still apply)
# "deny" -> block risky tools entirely (safe default for scheduled runs)
APPROVAL_MODE = os.getenv("AGENT_APPROVAL_MODE", "ask")

# Shell commands must start with one of these when in auto mode.
SHELL_ALLOWLIST = [
    c.strip() for c in os.getenv("SHELL_ALLOWLIST", "ls,cat,git status,git diff,git log,pytest,python").split(",") if c.strip()
]

# Optional: Telegram notifications for scheduled runs.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
