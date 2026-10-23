CREATE TABLE IF NOT EXISTS backups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name TEXT NOT NULL,
    stored_key TEXT NOT NULL,
    file_size INTEGER NOT NULL DEFAULT 0,
    checksum TEXT,
    status TEXT NOT NULL CHECK (status IN ('Success', 'Failed')),
    storage_mode TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'manual',
    error_message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recoveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id INTEGER,
    file_name TEXT NOT NULL,
    kind TEXT NOT NULL DEFAULT 'restore',
    status TEXT NOT NULL,
    checksum_match INTEGER,
    restored_file TEXT,
    message TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedule_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled INTEGER NOT NULL DEFAULT 0,
    interval_minutes INTEGER NOT NULL DEFAULT 60,
    last_run TEXT
);

INSERT OR IGNORE INTO schedule_settings (id, enabled, interval_minutes) VALUES (1, 0, 60);

CREATE INDEX IF NOT EXISTS idx_backups_name ON backups(file_name);