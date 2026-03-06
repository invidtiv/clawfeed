-- Migration 014: Digest Prompts
-- Stores prompt templates for digest generation, replacing file-based prompts.
-- Each group can reference a prompt_id. NULL means use the default prompt.

CREATE TABLE IF NOT EXISTS digest_prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  content TEXT NOT NULL,
  is_default INTEGER DEFAULT 0,
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

ALTER TABLE source_groups ADD COLUMN prompt_id INTEGER DEFAULT NULL;
