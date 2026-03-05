-- Migration 013: Track individual items per digest for deduplication
-- Stores the URL and title of each feed item included in a digest,
-- so future digests can filter already-seen items and inject recent context.

CREATE TABLE IF NOT EXISTS digest_items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  digest_id  INTEGER NOT NULL,
  group_id   INTEGER,
  item_url   TEXT    NOT NULL,
  item_title TEXT,
  created_at TEXT    DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_digest_items_group_time
  ON digest_items (group_id, created_at);
