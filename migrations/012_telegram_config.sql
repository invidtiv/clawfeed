-- Migration 012: Telegram configuration per source group
-- Adds telegram_thread_id (topic thread ID) and optional chat_id override per group

ALTER TABLE source_groups ADD COLUMN telegram_thread_id INTEGER DEFAULT NULL;
ALTER TABLE source_groups ADD COLUMN telegram_chat_id TEXT DEFAULT NULL;

-- Global Telegram defaults (bot token, default chat_id)
INSERT OR IGNORE INTO settings (key, value) VALUES ('telegram_bot_token', '""');
INSERT OR IGNORE INTO settings (key, value) VALUES ('telegram_chat_id', '""');
