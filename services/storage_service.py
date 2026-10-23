"""storage_service.py - the ONLY place that talks to storage.
LocalStorage = folder on your computer (development only, NOT cloud).
S3Storage    = real AWS S3 bucket.
"""
import logging
import shutil

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from config import Config
from utils.checksum import sha256_file
from utils.validators import safe_join

log = logging.getLogger(__name__)


class StorageError(Exception):
    pass


class LocalStorage:
    name = "local"

    def __init__(self):
        Config.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    def _path(self, key):
        return safe_join(Config.LOCAL_STORAGE_DIR, key)

    def upload(self, local_path, key, checksum):
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(local_path, dest)

    def verify(self, key, size, checksum):
        dest = self._path(key)
        return dest.exists() and dest.stat().st_size == size and sha256_file(dest) == checksum

    def download(self, key, dest_path):
        src = self._path(key)
        if not src.exists():
            raise StorageError("Backup copy not found in local storage.")
        shutil.copy2(src, dest_path)

    def exists(self, key):
        return self._path(key).exists()


class S3Storage:
    name = "aws"

    def __init__(self):
        self.bucket = Config.S3_BUCKET_NAME
        # No keys here: boto3 finds credentials itself (aws configure / IAM role).
        self.client = boto3.client("s3", region_name=Config.AWS_REGION)

    def upload(self, local_path, key, checksum):
        try:
            self.client.upload_file(
                str(local_path), self.bucket, key,
                ExtraArgs={"ServerSideEncryption": "AES256", "Metadata": {"sha256": checksum}},
            )
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"S3 upload failed: {exc}")

    def verify(self, key, size, checksum):
        try:
            head = self.client.head_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError):
            return False
        return head["ContentLength"] == size and head.get("Metadata", {}).get("sha256") == checksum

    def download(self, key, dest_path):
        try:
            self.client.download_file(self.bucket, key, str(dest_path))
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(f"S3 download failed: {exc}")

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise StorageError(f"S3 check failed: {exc}")


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        _storage = S3Storage() if Config.is_aws_mode() else LocalStorage()
        log.info("Storage backend: %s", _storage.name)
    return _storage