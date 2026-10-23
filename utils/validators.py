"""validators.py - file safety checks (type, size, unsafe paths)."""
import os
from pathlib import Path

from werkzeug.utils import secure_filename

from config import Config


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def validate_upload(file_storage):
    """Return (safe_name, error_message). error_message is None when the file is OK."""
    if file_storage is None or not file_storage.filename:
        return None, "No file selected."
    safe_name = secure_filename(file_storage.filename)  # removes ../ and odd characters
    if not safe_name or not allowed_file(safe_name):
        ext = safe_name.rsplit(".", 1)[-1] if "." in safe_name else "(none)"
        return None, f"File type '.{ext}' is not allowed."
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size == 0:
        return None, "File is empty."
    if size > Config.MAX_CONTENT_LENGTH:
        return None, f"File is larger than {Config.MAX_FILE_SIZE_MB} MB."
    return safe_name, None


def safe_join(base_dir, *parts):
    """Join paths but refuse to leave base_dir (blocks directory traversal)."""
    base = Path(base_dir).resolve()
    target = base.joinpath(*parts).resolve()
    if target != base and base not in target.parents:
        raise ValueError("Unsafe file path blocked.")
    return target