"""db.py - all SQLite code lives here."""
import sqlite3
from datetime import datetime

from config import Config


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    conn = sqlite3.connect(Config.DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def _execute(sql, params=()):
    conn = get_conn()
    try:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _query(sql, params=(), one=False):
    conn = get_conn()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def init_db():
    """Create the tables if they do not exist yet."""
    Config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_conn()
    try:
        conn.executescript(Config.SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


# ---------- backups ----------
def add_backup(file_name, stored_key, file_size, checksum, status, source, error_message=None):
    return _execute(
        "INSERT INTO backups (file_name, stored_key, file_size, checksum, status, "
        "storage_mode, source, error_message, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (file_name, stored_key, file_size, checksum, status,
         Config.STORAGE_MODE, source, error_message, now_str()),
    )


def get_backup(backup_id):
    return _query("SELECT * FROM backups WHERE id = ?", (backup_id,), one=True)


def list_backups(search="", status=""):
    sql = "SELECT * FROM backups WHERE 1=1"
    params = []
    if search:
        sql += " AND file_name LIKE ?"
        params.append(f"%{search}%")
    if status in ("Success", "Failed"):
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY id DESC"
    return _query(sql, params)


def latest_success_checksum(file_name):
    row = _query(
        "SELECT checksum FROM backups WHERE file_name = ? AND status = 'Success' "
        "ORDER BY id DESC LIMIT 1", (file_name,), one=True)
    return row["checksum"] if row else None


def get_stats():
    b = _query(
        "SELECT COUNT(CASE WHEN status='Success' THEN 1 END) AS ok, "
        "COUNT(CASE WHEN status='Failed' THEN 1 END) AS failed, "
        "COALESCE(SUM(CASE WHEN status='Success' THEN file_size END), 0) AS size, "
        "MAX(CASE WHEN status='Success' THEN created_at END) AS last_backup "
        "FROM backups", one=True)
    r = _query(
        "SELECT COUNT(*) AS total, COUNT(CASE WHEN status='Success' THEN 1 END) AS ok "
        "FROM recoveries WHERE kind = 'restore'", one=True)
    return {
        "files": b["ok"], "failed": b["failed"], "size": b["size"],
        "last_backup": b["last_backup"],
        "restores_total": r["total"], "restores_ok": r["ok"],
    }


def backups_per_day(limit=7):
    rows = _query(
        "SELECT substr(created_at,1,10) AS day, COUNT(*) AS n FROM backups "
        "WHERE status='Success' GROUP BY day ORDER BY day DESC LIMIT ?", (limit,))
    rows = list(reversed(rows))
    return [r["day"] for r in rows], [r["n"] for r in rows]


# ---------- recoveries ----------
def add_recovery(backup_id, file_name, kind, status, checksum_match, restored_file, message):
    match = None if checksum_match is None else int(bool(checksum_match))
    return _execute(
        "INSERT INTO recoveries (backup_id, file_name, kind, status, checksum_match, "
        "restored_file, message, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (backup_id, file_name, kind, status, match, restored_file, message, now_str()),
    )


def get_recovery(recovery_id):
    return _query("SELECT * FROM recoveries WHERE id = ?", (recovery_id,), one=True)


def list_recoveries(limit=20):
    return _query("SELECT * FROM recoveries ORDER BY id DESC LIMIT ?", (limit,))


def latest_simulation():
    return _query(
        "SELECT * FROM recoveries WHERE kind = 'simulation' ORDER BY id DESC LIMIT 1", one=True)


# ---------- schedule ----------
def get_schedule():
    return _query("SELECT * FROM schedule_settings WHERE id = 1", one=True)


def save_schedule(enabled, interval_minutes):
    _execute("UPDATE schedule_settings SET enabled = ?, interval_minutes = ? WHERE id = 1",
             (int(bool(enabled)), int(interval_minutes)))


def update_last_run():
    _execute("UPDATE schedule_settings SET last_run = ? WHERE id = 1", (now_str(),))