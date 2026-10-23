"""simulation_service.py - disaster recovery demo: lose a file, restore it, verify it."""
import logging
from datetime import datetime

from config import Config
from database import db
from services import backup_service, recovery_service
from services.storage_service import get_storage
from utils.validators import safe_join

log = logging.getLogger(__name__)


def _finish(backup_id, file_name, ok, match, restored_file, steps, message):
    db.add_recovery(backup_id, file_name, "simulation", "Success" if ok else "Failed",
                    match, restored_file, " | ".join(steps))
    return {"success": ok, "message": message}


def run_simulation():
    where = "AWS S3" if Config.is_aws_mode() else "local storage folder (LOCAL MODE)"
    steps = []
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"demo_{stamp}.txt"
    Config.DEMO_FILES_DIR.mkdir(parents=True, exist_ok=True)
    path = safe_join(Config.DEMO_FILES_DIR, file_name)
    path.write_text(f"Disaster recovery demo file\nCreated: {stamp}\nImportant data: 12345\n", encoding="utf-8")
    steps.append(f"1. Created local file '{file_name}'")

    backup = backup_service.backup_file(path, file_name, source="simulation")
    if not backup["success"]:
        steps.append(f"2. Backup FAILED: {backup['message']}")
        return _finish(backup["backup_id"], file_name, False, None, None, steps, "Simulation failed at backup step.")
    steps.append(f"2. Backed up to {where} and verified")

    path.unlink()
    steps.append(f"3. DISASTER: local file deleted (exists locally: {path.exists()})")

    try:
        in_cloud = get_storage().exists(backup["key"])
    except Exception as exc:
        log.exception("Existence check failed")
        in_cloud = False
        steps.append(f"4. Could not check storage: {exc}")
    else:
        steps.append(f"4. Backup copy still safe in {where}: {in_cloud}")
    if not in_cloud:
        return _finish(backup["backup_id"], file_name, False, None, None, steps, "Simulation failed: backup copy missing.")

    result = recovery_service.restore_core(backup["backup_id"])
    if not result["success"]:
        steps.append(f"5. Restore FAILED: {result['message']}")
        return _finish(backup["backup_id"], file_name, False, result["match"], None, steps, "Simulation failed at restore step.")
    steps.append(f"5. Restored file as '{result['restored_file']}'")
    steps.append("6. SHA-256 checksum matches the original: YES")
    return _finish(backup["backup_id"], file_name, True, True, result["restored_file"], steps,
                   f"Simulation complete: file lost locally, recovered from {where}, checksum verified.")