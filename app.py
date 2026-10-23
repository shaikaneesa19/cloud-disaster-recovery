"""app.py - Flask routes. Business logic lives in services/."""
import logging
import shutil
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_file, url_for
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from database import db
from services import backup_service, recovery_service, scheduler_service, simulation_service
from utils.validators import safe_join, validate_upload

# ---------- startup checks ----------
problems = Config.problems()
if problems:
    raise SystemExit("Fix these settings in .env first:\n- " + "\n- ".join(problems))

Config.ensure_directories()
_fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
_file = RotatingFileHandler(Config.LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
_file.setFormatter(_fmt)
_console = logging.StreamHandler()
_console.setFormatter(_fmt)
logging.basicConfig(level=logging.INFO, handlers=[_file, _console])
log = logging.getLogger("app")

db.init_db()

app = Flask(__name__)
app.config["SECRET_KEY"] = Config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH


@app.context_processor
def inject_globals():
    return {"is_aws": Config.is_aws_mode(), "mode_label": Config.mode_label(),
            "max_mb": Config.MAX_FILE_SIZE_MB}


@app.template_filter("filesize")
def filesize(num):
    num = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.2f} {unit}"
        num /= 1024


def _flash_result(result):
    flash(result["message"], "success" if result["success"] else "danger")


# ---------- pages ----------
@app.get("/")
def index():
    return render_template("index.html", stats=db.get_stats())


@app.get("/dashboard")
def dashboard():
    stats = db.get_stats()
    days, counts = db.backups_per_day()
    sim = db.latest_simulation()
    sim_steps = sim["message"].split(" | ") if sim and sim["message"] else []
    chart = {"ok": stats["files"], "failed": stats["failed"], "days": days, "counts": counts}
    return render_template("dashboard.html", stats=stats, chart=chart,
                           schedule=db.get_schedule(), next_run=scheduler_service.next_run_time(),
                           sim=sim, sim_steps=sim_steps)


@app.get("/history")
def history():
    q = request.args.get("q", "").strip()[:100]
    status = request.args.get("status", "")
    return render_template("history.html", backups=db.list_backups(q, status),
                           recoveries=db.list_recoveries(), q=q, status=status)


# ---------- actions ----------
@app.post("/upload")
def upload():
    files = request.files.getlist("files")
    if not files or all(not f.filename for f in files):
        flash("Please choose at least one file.", "warning")
        return redirect(url_for("dashboard"))
    for f in files:
        safe_name, error = validate_upload(f)
        if error:
            flash(f"{f.filename}: {error}", "danger")
            continue
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            tmp_path = tmp_dir / safe_name
            f.save(tmp_path)
            result = backup_service.backup_file(tmp_path, safe_name, source="manual")
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        _flash_result(result)
    return redirect(url_for("dashboard"))


@app.post("/restore/<int:backup_id>")
def restore(backup_id):
    _flash_result(recovery_service.restore_backup(backup_id))
    return redirect(url_for("history"))


@app.post("/verify/<int:backup_id>")
def verify(backup_id):
    _flash_result(recovery_service.verify_backup(backup_id))
    return redirect(url_for("history"))


@app.get("/download/<int:recovery_id>")
def download(recovery_id):
    rec = db.get_recovery(recovery_id)
    if not rec or rec["status"] != "Success" or not rec["restored_file"]:
        flash("No restored file available for that record.", "danger")
        return redirect(url_for("history"))
    try:
        path = safe_join(Config.RESTORED_FILES_DIR, rec["restored_file"])
    except ValueError:
        flash("Unsafe file path blocked.", "danger")
        return redirect(url_for("history"))
    if not path.exists():
        flash("The restored file is no longer on disk. Restore it again.", "warning")
        return redirect(url_for("history"))
    return send_file(path, as_attachment=True, download_name=rec["file_name"])


@app.post("/schedule")
def schedule():
    enabled = request.form.get("enabled") == "on"
    try:
        interval = int(request.form.get("interval", ""))
    except ValueError:
        flash("Interval must be a whole number of minutes.", "danger")
        return redirect(url_for("dashboard"))
    if not 1 <= interval <= 1440:
        flash("Interval must be between 1 and 1440 minutes.", "danger")
        return redirect(url_for("dashboard"))
    db.save_schedule(enabled, interval)
    scheduler_service.apply_schedule()
    flash(f"Scheduled backups {'ON, every ' + str(interval) + ' minute(s)' if enabled else 'OFF'}.", "success")
    return redirect(url_for("dashboard"))


@app.post("/schedule/run-now")
def schedule_run_now():
    summary = scheduler_service.run_now()
    if summary is None:
        flash("A scheduled backup is already running.", "warning")
    else:
        flash(f"Watched folder backup done: {summary['backed_up']} backed up, "
              f"{summary['skipped']} unchanged (skipped), {summary['failed']} failed.", "info")
    return redirect(url_for("dashboard"))


@app.post("/simulate")
def simulate():
    _flash_result(simulation_service.run_simulation())
    return redirect(url_for("dashboard"))


@app.errorhandler(RequestEntityTooLarge)
def too_large(_error):
    flash(f"Upload too large. Maximum is {Config.MAX_FILE_SIZE_MB} MB per request.", "danger")
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    scheduler_service.start_scheduler()
    # use_reloader=False so the scheduler is not started twice
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)