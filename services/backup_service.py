"""backup_service.py - backup logic. A backup is 'Success' ONLY after it is verified."""
import logging
from datetime import datetime
from pathlib import Path

from werkzeug.utils import secure_filename

from config import Config
from database import db
from services.storage_service import StorageError, get_storage
from utils.checksum import sha256_file
from utils.validators import allowed_file

log = logging.getLogger(__name__)


def backup_file(local_path, file_name, source="manual"):
    """Back up one file. Returns dict(success, message, backup_id, key, checksum)."""
    local_path = Path(local_path)
    key = f"{Config.S3_KEY_PREFIX}/{datetime.now():%Y%m%d_%H%M%S_%f}_{file_name}"
    size, checksum = 0, None
    where = "AWS S3" if Config.is_aws_mode() else "local storage (LOCAL MODE)"
    try:
        size = local_path.stat().st_size
        checksum = sha256_file(local_path)           # fingerprint BEFORE upload
        storage = get_storage()
        storage.upload(local_path, key, checksum)
        if not storage.verify(key, size, checksum):  # prove it was really stored
            raise StorageError("Upload could not be verified (size or checksum mismatch).")
        backup_id = db.add_backup(file_name, key, size, checksum, "Success", source)
        log.info("Backup OK: %s -> %s", file_name, key)
        return {"success": True, "backup_id": backup_id, "key": key, "checksum": checksum,
                "message": f"'{file_name}' backed up and verified in {where}."}
    except Exception as exc:
        log.exception("Backup failed for %s", file_name)
        backup_id = db.add_backup(file_name, key, size, checksum, "Failed", source, str(exc))
        return {"success": False, "backup_id": backup_id, "key": key, "checksum": checksum,
                "message": f"Backup FAILED for '{file_name}': {exc}"}


def backup_folder(folder=None, source="scheduled"):
    """Back up every allowed file in a folder. Unchanged files are skipped."""
    folder = Path(folder or Config.WATCHED_FOLDER)
    summary = {"backed_up": 0, "skipped": 0, "failed": 0}
    for path in sorted(folder.iterdir()):
        name = secure_filename(path.name)
        if not path.is_file() or not name or not allowed_file(name):
            continue
        if path.stat().st_size == 0 or path.stat().st_size > Config.MAX_CONTENT_LENGTH:
            continue
        if db.latest_success_checksum(name) == sha256_file(path):
            summary["skipped"] += 1
            continue
        result = backup_file(path, name, source=source)
        summary["backed_up" if result["success"] else "failed"] += 1
    log.info("Folder backup finished: %s", summary)
    return summary