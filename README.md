# CloudVault DR: Cloud-Based Disaster Recovery and Backup System

A web application that backs up files to cloud storage (AWS S3) and recovers them after accidental deletion, corruption or loss. Every file is fingerprinted with **SHA-256** before upload and checked again after recovery, so you can prove a restored file is identical to the original.

> Built with Python, Flask, AWS S3 (Boto3), SQLite and Bootstrap.

## Features

- **Dashboard:** total files backed up, storage used, successful vs failed backups, last backup time, and charts
- **File backup:** upload one or many files, with type and size validation
- **Backup history:** searchable, filterable table of every backup, with a recovery log
- **Restore and download:** one-click restore from storage, with a record of every recovery
- **Checksum verification:** SHA-256 calculated before upload and re-checked on restore. Corrupted copies are detected and discarded
- **Verify without restoring:** re-download a stored copy and compare its checksum
- **Scheduled backups:** configurable interval, backs up a watched folder, skips unchanged files, and prevents overlapping runs
- **Disaster recovery simulation:** creates a file, backs it up, deletes it locally, confirms the cloud copy exists, restores it and verifies the checksum
- **Honest storage modes:** a clearly labeled **LOCAL MODE** for development and **AWS S3** mode for real cloud storage

A backup is marked **Success** only after the stored copy has been verified. Otherwise it is recorded as **Failed** with the error.

## Architecture

```
Browser (Bootstrap dashboard)
        |
        v
Flask app (app.py: routes only)
   |            |             |
   v            v             v
SQLite      Services       Scheduler
(metadata)  backup / recovery / simulation   (APScheduler)
                |
                v
        storage_service
        |             |
        v             v
   AWS S3 (boto3)   Local folder (dev only)
```

The browser never talks to AWS. Only the Flask backend does, so no credentials reach the frontend.

## Tech stack

| Area | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript, Bootstrap 5, Chart.js |
| Backend | Python, Flask |
| Cloud storage | AWS S3 via Boto3 |
| Database | SQLite (backup and recovery metadata) |
| Scheduling | APScheduler |
| Testing | pytest, moto (mock AWS, tests only) |
| Version control | Git and GitHub |

## Project structure

```
cloud-disaster-recovery/
├── app.py                   # Flask routes
├── config.py                # Settings from environment variables
├── requirements.txt
├── .env.example             # Safe settings template
├── database/                # SQLite schema and queries
├── services/
│   ├── storage_service.py   # S3 and local storage
│   ├── backup_service.py    # Upload, verify, record
│   ├── recovery_service.py  # Restore, verify checksum
│   ├── scheduler_service.py # Scheduled backups
│   └── simulation_service.py# Disaster recovery demo
├── utils/                   # SHA-256 and file validation
├── templates/               # HTML pages
├── static/                  # CSS and JavaScript
└── tests/                   # Automated tests
```

## Getting started (Windows, PowerShell)

**Requirements:** Python 3.11 or newer, Git.

```powershell
git clone https://github.com/shaikaneesa19/cloud-disaster-recovery.git
cd cloud-disaster-recovery
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create your `.env` file (this generates a random secret key):

```powershell
$key = python -c "import secrets; print(secrets.token_hex(32))"
@"
SECRET_KEY=$key
STORAGE_MODE=local
AWS_REGION=ap-south-1
S3_BUCKET_NAME=
S3_KEY_PREFIX=backups
MAX_FILE_SIZE_MB=10
DEFAULT_BACKUP_INTERVAL_MINUTES=60
"@ | Set-Content -Path .env -Encoding ascii
```

Run the app:

```powershell
python app.py
```

Open http://127.0.0.1:5000

## Using real AWS S3

1. Create an S3 bucket with **Block all public access** on, **versioning** on and default encryption on.
2. Create an IAM user with a least-privilege policy (replace the bucket name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"},
    {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject"], "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/backups/*"}
  ]
}
```

3. Store credentials outside the project with `aws configure` (AWS CLI). Never put keys in code or `.env`.
4. In `.env`, set `STORAGE_MODE=aws`, `AWS_REGION` and `S3_BUCKET_NAME`, then restart the app.

The navigation bar shows **AWS S3 (cloud)** when real cloud storage is active. On AWS EC2, use an IAM role instead of access keys. Check the current AWS Free Tier terms before creating resources, and delete test resources when you are done.

## Running tests

```powershell
python -m pytest -q
```

The tests cover backup and restore, corruption detection, failed-backup recording, input validation and the S3 code path. The S3 test uses a mock AWS service (moto) and never contacts real AWS.

## Security

- No credentials in source code. Settings come from environment variables, and `.env` is excluded from Git
- Boto3 finds AWS credentials from the AWS CLI configuration or an IAM role
- File type allow-list, size limit and safe file names (`secure_filename`)
- Directory traversal protection on every storage and download path
- Server-side encryption (AES256) on uploaded objects
- Least-privilege IAM policy with no delete permission
- The development server listens on localhost only

## Backup vs disaster recovery vs business continuity

- **File backup:** making a copy of data. "I have a spare copy."
- **Disaster recovery:** the tools and plan to restore systems and data after a failure. "My files are gone, and here is how I get them back, verified."
- **Business continuity:** keeping the whole organization running during and after a disaster.

This project covers backup and disaster recovery for files.

## Limitations and future work

- No user login or CSRF protection yet
- Uploads are validated by extension and size, not by scanning file contents
- SQLite and an in-process scheduler suit a single instance. A larger deployment would use PostgreSQL and a separate worker
- Planned: user accounts, email alerts on failed backups, S3 lifecycle rules, and deployment on AWS EC2 with an IAM role

## Screenshots

<!-- Add screenshots to docs/screenshots/ and uncomment:
![Dashboard](docs/screenshots/dashboard.png)
![History](docs/screenshots/history.png)
-->

## License

Released for learning and portfolio use.