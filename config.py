"""
config.py - one central place for all application settings.

Settings come from environment variables (loaded from the .env file).
AWS access keys are NEVER read or stored here. Boto3 finds them on its own
(from `aws configure` locally, or from an IAM role on EC2).
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _get_int(name: str, default: int) -> int:
    """Read an integer environment variable safely."""
    raw = os.getenv(name, "").strip()
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


class Config:
    # ---- Security ----
    SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

    # ---- Storage mode: "local" or "aws" ----
    STORAGE_MODE = os.getenv("STORAGE_MODE", "local").strip().lower()

    # ---- AWS settings (used only in aws mode) ----
    AWS_REGION = os.getenv("AWS_REGION", "ap-south-1").strip()
    S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "").strip()
    S3_KEY_PREFIX = os.getenv("S3_KEY_PREFIX", "backups").strip().strip("/")

    # ---- Upload rules ----
    MAX_FILE_SIZE_MB = _get_int("MAX_FILE_SIZE_MB", 10)
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024  # Flask rejects bigger requests
    ALLOWED_EXTENSIONS = {
        "txt", "md", "csv", "json", "pdf",
        "png", "jpg", "jpeg", "gif",
        "doc", "docx", "xls", "xlsx", "ppt", "pptx",
        "zip",
    }

    # ---- Scheduler ----
    DEFAULT_BACKUP_INTERVAL_MINUTES = _get_int("DEFAULT_BACKUP_INTERVAL_MINUTES", 60)

    # ---- Folders and files ----
    DATABASE_PATH = BASE_DIR / "instance" / "backup.db"
    SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
    LOCAL_STORAGE_DIR = BASE_DIR / "local_storage"
    WATCHED_FOLDER = BASE_DIR / "watched_folder"
    DEMO_FILES_DIR = BASE_DIR / "demo_files"
    RESTORED_FILES_DIR = BASE_DIR / "restored_files"
    LOGS_DIR = BASE_DIR / "logs"
    LOG_FILE = LOGS_DIR / "app.log"

    @classmethod
    def is_aws_mode(cls) -> bool:
        return cls.STORAGE_MODE == "aws"

    @classmethod
    def mode_label(cls) -> str:
        """Text shown on screen so we never pretend local mode is the cloud."""
        return "AWS S3 (cloud)" if cls.is_aws_mode() else "LOCAL MODE (not cloud)"

    @classmethod
    def problems(cls) -> list:
        """Return a list of configuration mistakes (empty list = all good)."""
        issues = []
        if not cls.SECRET_KEY or cls.SECRET_KEY in ("change-me", "PASTE_YOUR_GENERATED_KEY_HERE"):
            issues.append("SECRET_KEY is missing. Generate one and put it in .env")
        if cls.STORAGE_MODE not in ("local", "aws"):
            issues.append("STORAGE_MODE must be 'local' or 'aws'")
        if cls.is_aws_mode() and not cls.S3_BUCKET_NAME:
            issues.append("S3_BUCKET_NAME is required when STORAGE_MODE=aws")
        if cls.MAX_FILE_SIZE_MB <= 0:
            issues.append("MAX_FILE_SIZE_MB must be greater than 0")
        return issues

    @classmethod
    def ensure_directories(cls) -> None:
        """Create the data folders if they are missing."""
        for folder in (
            cls.LOCAL_STORAGE_DIR,
            cls.WATCHED_FOLDER,
            cls.DEMO_FILES_DIR,
            cls.RESTORED_FILES_DIR,
            cls.LOGS_DIR,
            cls.DATABASE_PATH.parent,
        ):
            folder.mkdir(parents=True, exist_ok=True)