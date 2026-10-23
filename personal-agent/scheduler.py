"""Runs recurring jobs unattended. Edit JOBS to taste, then: python scheduler.py

Scheduled runs should use AGENT_APPROVAL_MODE=deny (read-only) or auto with a
tight SHELL_ALLOWLIST. Results are pushed to Telegram if configured.
"""
import logging

import httpx
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

import agent
import config

logging.basicConfig(level=logging.INFO)
TZ = "Asia/Dhaka"

JOBS = [
    {"id": "morning-brief", "cron": "0 8 * * *",
     "task": "Read my unread email, list the 5 most important with a one-line summary each, "
             "then search the web for top headlines in AI and technology. Save the combined brief "
             "to briefs/today.md and give me a short summary."},
    {"id": "inbox-triage", "cron": "0 13,18 * * 1-5",
     "task": "Check unread email and tell me only what needs a reply today. Do not send anything."},
    {"id": "workspace-tidy", "cron": "0 22 * * 0",
     "task": "List files in the workspace and suggest how to organize them. Do not move anything."},
]


def notify(text: str):
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        httpx.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                   data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000]})
    else:
        print(text)


def run_job(job):
    logging.info("running %s", job["id"])
    try:
        notify(f"[{job['id']}]\n" + agent.run(job["task"], verbose=False))
    except Exception as e:
        notify(f"[{job['id']}] failed: {e}")


if __name__ == "__main__":
    sched = BlockingScheduler(timezone=TZ)
    for j in JOBS:
        sched.add_job(run_job, CronTrigger.from_crontab(j["cron"], timezone=TZ), args=[j], id=j["id"])
    logging.info("Scheduler started with %d jobs", len(JOBS))
    sched.start()
