import pytest

from config import Config
from database import db
from services import backup_service, recovery_service, storage_service
from utils.validators import allowed_file, safe_join


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """Isolated local-mode setup so tests never touch your real data or AWS."""
    monkeypatch.setattr(Config, "STORAGE_MODE", "local")
    monkeypatch.setattr(Config, "DATABASE_PATH", tmp_path / "test.db")
    monkeypatch.setattr(Config, "LOCAL_STORAGE_DIR", tmp_path / "cloud")
    monkeypatch.setattr(Config, "RESTORED_FILES_DIR", tmp_path / "restored")
    monkeypatch.setattr(storage_service, "_storage", None)
    db.init_db()
    return tmp_path


def test_backup_then_restore_matches(env):
    f = env / "note.txt"
    f.write_text("hello disaster recovery")
    r = backup_service.backup_file(f, "note.txt")
    assert r["success"]
    rr = recovery_service.restore_backup(r["backup_id"])
    assert rr["success"] and rr["match"]


def test_corrupted_backup_is_detected(env):
    f = env / "data.txt"
    f.write_text("important")
    r = backup_service.backup_file(f, "data.txt")
    stored = Config.LOCAL_STORAGE_DIR / db.get_backup(r["backup_id"])["stored_key"]
    stored.write_bytes(b"tampered")
    rr = recovery_service.restore_backup(r["backup_id"])
    assert rr["success"] is False and rr["match"] is False


def test_missing_file_is_recorded_as_failed(env):
    r = backup_service.backup_file(env / "missing.txt", "missing.txt")
    assert r["success"] is False
    assert db.get_stats()["failed"] == 1


def test_validators_block_unsafe_input(env):
    assert not allowed_file("virus.exe")
    assert allowed_file("report.pdf")
    with pytest.raises(ValueError):
        safe_join(env, "..", "secret.txt")


def test_s3_roundtrip_with_moto(env, monkeypatch):
    """Uses moto (a fake AWS) ONLY inside tests to check the S3 code path."""
    boto3 = pytest.importorskip("boto3")
    moto = pytest.importorskip("moto")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with moto.mock_aws():
        boto3.client("s3", region_name="us-east-1").create_bucket(Bucket="test-bucket")
        monkeypatch.setattr(Config, "STORAGE_MODE", "aws")
        monkeypatch.setattr(Config, "AWS_REGION", "us-east-1")
        monkeypatch.setattr(Config, "S3_BUCKET_NAME", "test-bucket")
        monkeypatch.setattr(storage_service, "_storage", None)
        f = env / "cloud.txt"
        f.write_text("cloud data")
        r = backup_service.backup_file(f, "cloud.txt")
        assert r["success"]
        rr = recovery_service.restore_backup(r["backup_id"])
        assert rr["success"] and rr["match"]