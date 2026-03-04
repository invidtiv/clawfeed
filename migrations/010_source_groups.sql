-- Migration 010: Source Groups and Settings
-- Add source groups for organizing sources into categories (Tech, Status, News, etc.)
-- Add group_id to sources and digests tables
-- Add system settings table

-- Source Groups table
CREATE TABLE IF NOT EXISTS source_groups (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  description TEXT DEFAULT '',
  digest_types TEXT DEFAULT '[]', -- JSON array: ["4h", "daily", "weekly"]
  timezone TEXT DEFAULT 'UTC',
  schedule TEXT DEFAULT '{}', -- JSON object with schedule config
  is_active INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_source_groups_active ON source_groups(is_active);

-- Add group_id to sources table
ALTER TABLE sources ADD COLUMN group_id INTEGER REFERENCES source_groups(id);
CREATE INDEX IF NOT EXISTS idx_sources_group_id ON sources(group_id);

-- Add group_id to digests table to track which group generated the digest
ALTER TABLE digests ADD COLUMN group_id INTEGER REFERENCES source_groups(id);
CREATE INDEX IF NOT EXISTS idx_digests_group_id ON digests(group_id);

-- System settings table (for global app settings like timezone)
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT DEFAULT (datetime('now'))
);

-- Insert default settings
INSERT OR IGNORE INTO settings (key, value) VALUES ('global_timezone', '"UTC"');
INSERT OR IGNORE INTO settings (key, value) VALUES ('default_language', '"en"');
