"""scheduler_service.py - automatic backups of watched_folder.
No duplicate runs: one job id + max_instances=1 + a lock + no Flask reloader.
"""
import logging
import threading

from apscheduler.schedulers.background import BackgroundScheduler

from database import db
from services.backup_service import backup_folder

log = logging.getLogger(__name__)

JOB_ID = "scheduled_backup"
_scheduler = BackgroundScheduler()
_lock = threading.Lock()


def _job():
    if not _lock.acquire(blocking=False):
        log.warning("Previous backup run still active - skipping this one.")
        return None
    try:
        summary = backup_folder()
        db.update_last_run()
        return summary
    finally:
        _lock.release()


def apply_schedule():
    """Make the scheduler match the saved settings."""
    s = db.get_schedule()
    if s["enabled"]:
        _scheduler.add_job(_job, "interval", minutes=s["interval_minutes"], id=JOB_ID,
                           replace_existing=True, max_instances=1, coalesce=True)
        log.info("Scheduled backup every %s minute(s)", s["interval_minutes"])
    elif _scheduler.get_job(JOB_ID):
        _scheduler.remove_job(JOB_ID)
        log.info("Scheduled backup disabled")


def start_scheduler():
    if not _scheduler.running:
        _scheduler.start()
    apply_schedule()


def next_run_time():
    job = _scheduler.get_job(JOB_ID)
    if job and job.next_run_time:
        return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    return None


def run_now():
    return _job()