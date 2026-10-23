# Personal Agent

A tool-using agent on the Claude API. Covers email, research, files and dev tasks, with a scheduler for unattended runs.

## Setup

    python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env     # add ANTHROPIC_API_KEY and email app password

## Use

    python agent.py                      # interactive chat
    python agent.py "summarize my unread email"
    python scheduler.py                  # run scheduled jobs (edit JOBS inside)

## Layout

- `agent.py`: the loop (model call, tool execution, approval gate, audit log)
- `tools.py`: tools. Add one with the `@tool(...)` decorator; mark `risky=True` if it changes anything
- `scheduler.py`: cron-style jobs, Telegram notifications
- `config.py`: all settings from `.env`
- `data/audit.log`: every task, tool call and denial (JSON lines)
- `data/memory.json`: long-term memory

## Safety model ("full automation" without surprises)

- File access is confined to `./workspace`.
- Risky tools (`write_file`, `send_email`, `run_shell`) pass through `AGENT_APPROVAL_MODE`:
  `ask` prompts you, `deny` blocks them, `auto` runs them (shell limited to `SHELL_ALLOWLIST`).
- Email reading uses `BODY.PEEK` and a read-only mailbox, so nothing gets marked as read.
- The system prompt tells the model that email, web and file content is data, not instructions.
  This reduces prompt-injection risk but does not remove it. Keep unattended jobs read-only
  unless you trust every input source.
- `AGENT_MAX_STEPS` caps runaway loops.

## Suggested path to full automation

1. Run in `ask` mode for a week and read `data/audit.log`.
2. Move recurring read-only jobs to the scheduler with `deny`.
3. Switch specific jobs to `auto` only after you've seen the actions are always what you expect.

## Running 24/7

Put `python scheduler.py` under systemd, Docker, or a small VPS.
