"""Tool implementations and their JSON schemas.

Each tool is registered with @tool(...). `risky=True` tools go through the
approval policy in config.APPROVAL_MODE before running.
"""
from __future__ import annotations

import email
import imaplib
import json
import shlex
import smtplib
import subprocess
from email.header import decode_header
from email.message import EmailMessage
from typing import Callable

import httpx
from bs4 import BeautifulSoup

import config

REGISTRY: dict[str, dict] = {}


def tool(name: str, description: str, properties: dict, required: list[str], risky: bool = False):
    def deco(fn: Callable):
        REGISTRY[name] = {
            "fn": fn,
            "risky": risky,
            "schema": {
                "name": name,
                "description": description,
                "input_schema": {"type": "object", "properties": properties, "required": required},
            },
        }
        return fn

    return deco


def schemas() -> list[dict]:
    return [t["schema"] for t in REGISTRY.values()]


# ---------------------------------------------------------------- files ----
def _safe_path(rel: str):
    p = (config.WORKSPACE / rel).resolve()
    if config.WORKSPACE != p and config.WORKSPACE not in p.parents:
        raise PermissionError(f"Path escapes workspace: {rel}")
    return p


@tool("list_files", "List files in the workspace directory (or a subfolder).",
      {"path": {"type": "string", "description": "Relative folder, default '.'"}}, [])
def list_files(path: str = "."):
    base = _safe_path(path)
    return "\n".join(sorted(str(p.relative_to(config.WORKSPACE)) for p in base.rglob("*") if p.is_file())[:500]) or "(empty)"


@tool("read_file", "Read a text file from the workspace.",
      {"path": {"type": "string"}}, ["path"])
def read_file(path: str):
    return _safe_path(path).read_text(errors="replace")[:50_000]


@tool("write_file", "Create or overwrite a text file in the workspace.",
      {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"], risky=True)
def write_file(path: str, content: str):
    p = _safe_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return f"Wrote {len(content)} chars to {path}"


# ------------------------------------------------------------------ web ----
@tool("fetch_url", "Fetch a web page and return its readable text.",
      {"url": {"type": "string"}}, ["url"])
def fetch_url(url: str):
    r = httpx.get(url, follow_redirects=True, timeout=20, headers={"User-Agent": "personal-agent/1.0"})
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "nav", "footer"]):
        t.decompose()
    text = " ".join(soup.get_text(" ").split())
    return text[:20_000]


@tool("web_search", "Search the web via DuckDuckGo HTML and return top results (title, url).",
      {"query": {"type": "string"}}, ["query"])
def web_search(query: str):
    r = httpx.post("https://html.duckduckgo.com/html/", data={"q": query}, timeout=20,
                   headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a.result__a")[:8]:
        out.append(f"{a.get_text(strip=True)} -- {a.get('href')}")
    return "\n".join(out) or "No results."


# ---------------------------------------------------------------- email ----
def _decode(h):
    parts = decode_header(h or "")
    return "".join(p.decode(enc or "utf-8", errors="replace") if isinstance(p, bytes) else p for p, enc in parts)


@tool("read_inbox", "Read the most recent unread emails (sender, subject, short body).",
      {"limit": {"type": "integer", "description": "Max emails, default 10"}}, [])
def read_inbox(limit: int = 10):
    if not config.EMAIL_USER:
        return "Email not configured. Set EMAIL_USER and EMAIL_PASS."
    with imaplib.IMAP4_SSL(config.IMAP_HOST) as m:
        m.login(config.EMAIL_USER, config.EMAIL_PASS)
        m.select("INBOX", readonly=True)  # readonly: never marks mail as read
        _, data = m.search(None, "UNSEEN")
        ids = data[0].split()[-limit:]
        out = []
        for i in reversed(ids):
            _, msg_data = m.fetch(i, "(BODY.PEEK[])")
            msg = email.message_from_bytes(msg_data[0][1])
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors="replace")
            out.append({"from": _decode(msg["From"]), "subject": _decode(msg["Subject"]),
                        "date": msg["Date"], "body": " ".join(body.split())[:800]})
        return json.dumps(out, indent=2) if out else "No unread email."


@tool("send_email", "Send an email. Always requires approval.",
      {"to": {"type": "string"}, "subject": {"type": "string"}, "body": {"type": "string"}},
      ["to", "subject", "body"], risky=True)
def send_email(to: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = config.EMAIL_USER, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.login(config.EMAIL_USER, config.EMAIL_PASS)
        s.send_message(msg)
    return f"Sent to {to}"


# ---------------------------------------------------------------- shell ----
@tool("run_shell", "Run a shell command inside the workspace directory. Output is truncated.",
      {"command": {"type": "string"}}, ["command"], risky=True)
def run_shell(command: str):
    if config.APPROVAL_MODE == "auto" and not any(command.startswith(a) for a in config.SHELL_ALLOWLIST):
        return f"Blocked: command not in SHELL_ALLOWLIST ({config.SHELL_ALLOWLIST})."
    p = subprocess.run(shlex.split(command), cwd=config.WORKSPACE, capture_output=True, text=True, timeout=120)
    return (p.stdout + p.stderr)[-8000:] or f"(exit {p.returncode})"


# --------------------------------------------------------------- memory ----
def _mem() -> dict:
    return json.loads(config.MEMORY_FILE.read_text()) if config.MEMORY_FILE.exists() else {}


@tool("remember", "Save a fact or preference to long-term memory under a key.",
      {"key": {"type": "string"}, "value": {"type": "string"}}, ["key", "value"])
def remember(key: str, value: str):
    m = _mem()
    m[key] = value
    config.MEMORY_FILE.write_text(json.dumps(m, indent=2))
    return "Saved."


@tool("recall", "Return everything in long-term memory.", {}, [])
def recall():
    return json.dumps(_mem(), indent=2) or "{}"
