-- Remove CHECK constraint on digests.type to allow custom digest types like '4h-tech', '4h-status', etc.
-- SQLite doesn't support dropping constraints directly, so we need to recreate the table

-- Create new table without the type constraint
CREATE TABLE IF NOT EXISTS digests_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  metadata TEXT DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  group_id INTEGER REFERENCES source_groups(id)
);

-- Copy data from old table
INSERT INTO digests_new (id, type, content, metadata, created_at, group_id)
SELECT id, type, content, metadata, created_at, group_id FROM digests;

-- Drop old table
DROP TABLE digests;

-- Rename new table
ALTER TABLE digests_new RENAME TO digests;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_digests_type ON digests(type);
CREATE INDEX IF NOT EXISTS idx_digests_created ON digests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_digests_group ON digests(group_id);
