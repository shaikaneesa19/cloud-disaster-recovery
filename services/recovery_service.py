"""recovery_service.py - restore + verify files."""
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from config import Config
from database import db
from services.storage_service import get_storage
from utils.checksum import sha256_file
from utils.validators import safe_join

log = logging.getLogger(__name__)


def _result(success, match, file_name, restored_file, message):
    return {"success": success, "match": match, "file_name": file_name,
            "restored_file": restored_file, "message": message}


def restore_core(backup_id):
    """Download a backup and verify its SHA-256. Does NOT write to the recovery log."""
    rec = db.get_backup(backup_id)
    if rec is None:
        return _result(False, None, "unknown", None, "Backup record not found.")
    if rec["status"] != "Success":
        return _result(False, None, rec["file_name"], None, "Only successful backups can be restored.")

    restored_name = f"restored_{datetime.now():%Y%m%d_%H%M%S}_{rec['file_name']}"
    dest = None
    try:
        Config.RESTORED_FILES_DIR.mkdir(parents=True, exist_ok=True)
        dest = safe_join(Config.RESTORED_FILES_DIR, restored_name)
        get_storage().download(rec["stored_key"], dest)
        actual = sha256_file(dest)
    except Exception as exc:
        log.exception("Restore failed for backup %s", backup_id)
        if dest is not None:
            dest.unlink(missing_ok=True)
        return _result(False, None, rec["file_name"], None, f"Restore failed: {exc}")

    if actual != rec["checksum"]:
        dest.unlink(missing_ok=True)
        return _result(False, False, rec["file_name"], None,
                       "WARNING: checksum mismatch. The downloaded file differs from the original and was discarded.")
    return _result(True, True, rec["file_name"], restored_name,
                   f"Restored '{rec['file_name']}'. Checksum matches the original (SHA-256 verified).")


def restore_backup(backup_id):
    result = restore_core(backup_id)
    result["recovery_id"] = db.add_recovery(
        backup_id, result["file_name"], "restore",
        "Success" if result["success"] else "Failed",
        result["match"], result["restored_file"], result["message"])
    return result


def verify_backup(backup_id):
    """Download the stored copy to a temp folder and compare its checksum (no restore)."""
    rec = db.get_backup(backup_id)
    if rec is None or rec["status"] != "Success":
        return {"success": False, "message": "Only successful backups can be verified."}
    tmp_dir = Path(tempfile.mkdtemp())
    try:
        tmp_file = tmp_dir / "verify.bin"
        get_storage().download(rec["stored_key"], tmp_file)
        ok = sha256_file(tmp_file) == rec["checksum"]
    except Exception as exc:
        log.exception("Verify failed for backup %s", backup_id)
        return {"success": False, "message": f"Verification failed: {exc}"}
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    if ok:
        return {"success": True, "message": f"'{rec['file_name']}' verified: stored copy matches the original checksum."}
    return {"success": False, "message": f"'{rec['file_name']}' is CORRUPTED: checksum does not match."}