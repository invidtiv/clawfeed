import Database from 'better-sqlite3';
import { readFileSync, existsSync, readdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';
import env from './env.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

let _db;

function _runSqlIdempotent(db, sql) {
  for (const stmt of sql.split(';').map(s => s.trim()).filter(Boolean)) {
    try {
      db.exec(stmt + ';');
    } catch (e) {
      if (!e.message.includes('duplicate column') && !e.message.includes('already exists') && !e.message.includes('no such table')) {
        throw e;
      }
    }
  }
}

export function getDb(dbPath) {
  if (_db) return _db;
  const p = dbPath || join(ROOT, 'data', 'digest.db');
  _db = new Database(p);
  _db.pragma('journal_mode = WAL');
  _db.pragma('foreign_keys = ON');
  // Run migrations from all .sql files in sorted order
  const migrationsDir = join(ROOT, 'migrations');
  const migrationFiles = readdirSync(migrationsDir)
    .filter(f => f.endsWith('.sql'))
    .sort();
  for (const file of migrationFiles) {
    try {
      const sql = readFileSync(join(migrationsDir, file), 'utf8');
      _runSqlIdempotent(_db, sql);
    } catch (e) {
      if (!e.message.includes('duplicate column') && !e.message.includes('already exists') && !e.message.includes('no such table')) {
        console.error(`Migration ${file}:`, e.message);
      }
    }
  }

  // Seed prompts from template files on first run
  _seedPromptsFromFiles(_db);

  // Backfill slugs for existing users
  _backfillSlugs(_db);
  return _db;
}

function _generateSlug(email, name) {
  const base = (email ? email.split('@')[0] : name || 'user').toLowerCase();
  return base.replace(/[^a-z0-9_-]/g, '').slice(0, 30) || 'user';
}

function _backfillSlugs(db) {
  const users = db.prepare('SELECT id, email, name, slug FROM users WHERE slug IS NULL').all();
  // Special slug mappings
  const SLUG_MAP = { 'freefacefly@gmail.com': 'kevin', 'kevin@coco.xyz': 'kevinhe' };
  for (const u of users) {
    let slug = SLUG_MAP[u.email] || _generateSlug(u.email, u.name);
    let candidate = slug;
    let i = 1;
    while (db.prepare('SELECT 1 FROM users WHERE slug = ? AND id != ?').get(candidate, u.id)) {
      candidate = slug + i++;
    }
    db.prepare('UPDATE users SET slug = ? WHERE id = ?').run(candidate, u.id);
  }
}

// ── Digests ──

export function listDigests(db, { type, limit = 20, offset = 0, group_id } = {}) {
  let sql = 'SELECT digests.*, source_groups.name as group_name FROM digests LEFT JOIN source_groups ON digests.group_id = source_groups.id';
  const params = [];
  const conditions = [];
  if (type) { conditions.push('digests.type = ?'); params.push(type); }
  if (group_id !== undefined) {
    if (group_id === null) {
      conditions.push('digests.group_id IS NULL');
    } else {
      conditions.push('digests.group_id = ?');
      params.push(group_id);
    }
  }
  if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
  sql += ' ORDER BY digests.created_at DESC LIMIT ? OFFSET ?';
  params.push(limit, offset);
  return db.prepare(sql).all(...params);
}

export function getDigest(db, id) {
  return db.prepare('SELECT * FROM digests WHERE id = ?').get(id);
}

export function createDigest(db, { type, content, metadata = '{}', created_at, group_id }) {
  const cols = ['type', 'content', 'metadata'];
  const params = [type, content, metadata];
  if (created_at !== undefined) { cols.push('created_at'); params.push(created_at); }
  if (group_id !== undefined) { cols.push('group_id'); params.push(group_id); }
  const placeholders = cols.map(() => '?').join(', ');
  const result = db.prepare(`INSERT INTO digests (${cols.join(', ')}) VALUES (${placeholders})`).run(...params);
  return { id: result.lastInsertRowid };
}

// ── Marks ──

export function listMarks(db, { status, limit = 100, offset = 0, userId } = {}) {
  let sql = 'SELECT * FROM marks';
  const params = [];
  const conditions = [];
  if (status) { conditions.push('status = ?'); params.push(status); }
  if (userId) { conditions.push('user_id = ?'); params.push(userId); }
  if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
  sql += ' ORDER BY created_at DESC LIMIT ? OFFSET ?';
  params.push(limit, offset);
  return db.prepare(sql).all(...params);
}

export function createMark(db, { url, title = '', note = '', userId }) {
  // Check duplicate for this user
  const existing = db.prepare('SELECT id FROM marks WHERE url = ? AND user_id = ?').get(url, userId);
  if (existing) return { id: existing.id, duplicate: true };
  const result = db.prepare('INSERT INTO marks (url, title, note, user_id) VALUES (?, ?, ?, ?)').run(url, title, note, userId);
  return { id: result.lastInsertRowid, duplicate: false };
}

export function deleteMark(db, id, userId) {
  return db.prepare('DELETE FROM marks WHERE id = ? AND user_id = ?').run(id, userId);
}

export function migrateMarksToUser(db, userId) {
  return db.prepare('UPDATE marks SET user_id = ? WHERE user_id IS NULL').run(userId);
}

export function updateMarkStatus(db, id, status) {
  return db.prepare('UPDATE marks SET status = ? WHERE id = ?').run(status, id);
}

// ── Auth ──

export function upsertUser(db, { googleId, email, name, avatar }) {
  const existing = db.prepare('SELECT * FROM users WHERE google_id = ?').get(googleId);
  if (existing) {
    db.prepare('UPDATE users SET email = ?, name = ?, avatar = ? WHERE google_id = ?').run(email, name, avatar, googleId);
    // Backfill slug if missing
    if (!existing.slug) {
      let slug = _generateSlug(email, name);
      let candidate = slug;
      let i = 1;
      while (db.prepare('SELECT 1 FROM users WHERE slug = ? AND id != ?').get(candidate, existing.id)) {
        candidate = slug + i++;
      }
      db.prepare('UPDATE users SET slug = ? WHERE id = ?').run(candidate, existing.id);
    }
    return db.prepare('SELECT * FROM users WHERE google_id = ?').get(googleId);
  }
  let slug = _generateSlug(email, name);
  let candidate = slug;
  let i = 1;
  while (db.prepare('SELECT 1 FROM users WHERE slug = ?').get(candidate)) {
    candidate = slug + i++;
  }
  db.prepare('INSERT INTO users (google_id, email, name, avatar, slug) VALUES (?, ?, ?, ?, ?)').run(googleId, email, name, avatar, candidate);
  const newUser = db.prepare('SELECT * FROM users WHERE google_id = ?').get(googleId);
  // Auto-subscribe new user to all public sources
  db.prepare('INSERT OR IGNORE INTO user_subscriptions (user_id, source_id) SELECT ?, id FROM sources WHERE is_public = 1').run(newUser.id);
  return newUser;
}

export function createSession(db, { id, userId, expiresAt }) {
  db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').run(id, userId, expiresAt);
}

export function getSession(db, sessionId) {
  return db.prepare(`
    SELECT s.*, u.id as uid, u.google_id, u.email, u.name, u.avatar, u.slug
    FROM sessions s JOIN users u ON s.user_id = u.id
    WHERE s.id = ? AND s.expires_at > datetime('now')
  `).get(sessionId);
}

export function deleteSession(db, sessionId) {
  db.prepare('DELETE FROM sessions WHERE id = ?').run(sessionId);
}

// ── Feed ──

export function getUserBySlug(db, slug) {
  return db.prepare('SELECT id, name, slug, avatar FROM users WHERE slug = ?').get(slug);
}

export function listDigestsByUser(db, userId, { type, limit = 10, since } = {}) {
  // userId=null means system digests (user_id IS NULL), which we also show for any user feed
  let sql = 'SELECT id, type, content, created_at FROM digests WHERE (user_id = ? OR user_id IS NULL)';
  const params = [userId];
  if (type) { sql += ' AND type = ?'; params.push(type); }
  if (since) { sql += ' AND created_at >= ?'; params.push(since); }
  sql += ' ORDER BY created_at DESC LIMIT ?';
  params.push(Math.min(limit, 50));
  return db.prepare(sql).all(...params);
}

export function countDigestsByUser(db, userId, { type } = {}) {
  let sql = 'SELECT COUNT(*) as total FROM digests WHERE (user_id = ? OR user_id IS NULL)';
  const params = [userId];
  if (type) { sql += ' AND type = ?'; params.push(type); }
  return db.prepare(sql).get(...params).total;
}

// ── Sources ──

export function listSources(db, { activeOnly, userId, includePublic } = {}) {
  let sql = 'SELECT sources.*, users.name as creator_name, source_groups.name as group_name FROM sources LEFT JOIN users ON sources.created_by = users.id LEFT JOIN source_groups ON sources.group_id = source_groups.id';
  const conditions = ['sources.is_deleted = 0'];
  const params = [];
  if (activeOnly) { conditions.push('is_active = 1'); }
  if (userId && includePublic) {
    conditions.push('(created_by = ? OR is_public = 1)');
    params.push(userId);
  } else if (userId) {
    conditions.push('created_by = ?');
    params.push(userId);
  } else if (includePublic) {
    conditions.push('is_public = 1');
  }
  if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
  sql += ' ORDER BY created_at DESC';
  return db.prepare(sql).all(...params);
}

export function getSource(db, id) {
  return db.prepare('SELECT sources.*, source_groups.name as group_name FROM sources LEFT JOIN source_groups ON sources.group_id = source_groups.id WHERE sources.id = ?').get(id);
}

export function createSource(db, { name, type, config = '{}', isPublic = 0, createdBy }) {
  const result = db.prepare(
    'INSERT INTO sources (name, type, config, is_public, created_by) VALUES (?, ?, ?, ?, ?)'
  ).run(name, type, config, isPublic ? 1 : 0, createdBy);
  const sourceId = result.lastInsertRowid;
  // Auto-subscribe creator
  if (createdBy) {
    try {
      db.prepare('INSERT OR IGNORE INTO user_subscriptions (user_id, source_id) VALUES (?, ?)').run(createdBy, sourceId);
    } catch {}
  }
  return { id: sourceId };
}

export function updateSource(db, id, patch) {
  const allowed = ['name', 'type', 'config', 'is_active', 'is_public', 'group_id'];
  const sets = [];
  const params = [];
  for (const [k, v] of Object.entries(patch)) {
    const col = k === 'isActive' ? 'is_active' : k === 'isPublic' ? 'is_public' : k === 'groupId' ? 'group_id' : k;
    if (allowed.includes(col)) {
      sets.push(`${col} = ?`);
      params.push(typeof v === 'boolean' ? (v ? 1 : 0) : v);
    }
  }
  if (!sets.length) return { changes: 0 };
  sets.push("updated_at = datetime('now')");
  params.push(id);
  return db.prepare(`UPDATE sources SET ${sets.join(', ')} WHERE id = ?`).run(...params);
}

export function deleteSource(db, id, userId) {
  if (userId) {
    return db.prepare("UPDATE sources SET is_deleted = 1, deleted_at = datetime('now') WHERE id = ? AND created_by = ?").run(id, userId);
  }
  return db.prepare("UPDATE sources SET is_deleted = 1, deleted_at = datetime('now') WHERE id = ?").run(id);
}

export function getSourceByTypeConfig(db, type, config) {
  return db.prepare('SELECT * FROM sources WHERE type = ? AND config = ?').get(type, config);
}

// ── Source Packs ──

export function createPack(db, { name, description, slug, sourcesJson, createdBy }) {
  const result = db.prepare(
    'INSERT INTO source_packs (name, description, slug, sources_json, created_by) VALUES (?, ?, ?, ?, ?)'
  ).run(name, description || '', slug, sourcesJson, createdBy);
  return { id: result.lastInsertRowid };
}

export function getPack(db, id) {
  return db.prepare('SELECT * FROM source_packs WHERE id = ?').get(id);
}

export function getPackBySlug(db, slug) {
  return db.prepare('SELECT sp.*, u.name as creator_name, u.avatar as creator_avatar, u.slug as creator_slug FROM source_packs sp LEFT JOIN users u ON sp.created_by = u.id WHERE sp.slug = ?').get(slug);
}

export function listPacks(db, { publicOnly, userId } = {}) {
  let sql = 'SELECT sp.*, u.name as creator_name, u.avatar as creator_avatar, u.slug as creator_slug FROM source_packs sp LEFT JOIN users u ON sp.created_by = u.id';
  const conditions = [];
  const params = [];
  if (publicOnly && userId) {
    conditions.push('(sp.is_public = 1 OR sp.created_by = ?)');
    params.push(userId);
  } else if (publicOnly) {
    conditions.push('sp.is_public = 1');
  } else if (userId) {
    conditions.push('sp.created_by = ?');
    params.push(userId);
  }
  if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
  sql += ' ORDER BY sp.install_count DESC, sp.created_at DESC';
  return db.prepare(sql).all(...params);
}

export function incrementPackInstall(db, id) {
  return db.prepare("UPDATE source_packs SET install_count = install_count + 1, updated_at = datetime('now') WHERE id = ?").run(id);
}

export function deletePack(db, id) {
  return db.prepare('DELETE FROM source_packs WHERE id = ?').run(id);
}

// ── Subscriptions ──

export function listSubscriptions(db, userId) {
  return db.prepare(`
    SELECT s.*, us.created_at as subscribed_at, u.name as creator_name, s.is_deleted
    FROM user_subscriptions us
    JOIN sources s ON us.source_id = s.id
    LEFT JOIN users u ON s.created_by = u.id
    WHERE us.user_id = ?
    ORDER BY us.created_at DESC
  `).all(userId);
}

export function listUserSelections(db, userId, { includePrivate = false } = {}) {
  let sql = `
    SELECT
      s.id, s.name, s.type, s.config, s.is_public, s.is_active, s.created_by, s.updated_at,
      us.created_at as subscribed_at,
      u.name as creator_name,
      u.slug as creator_slug
    FROM user_subscriptions us
    JOIN sources s ON us.source_id = s.id
    LEFT JOIN users u ON s.created_by = u.id
    WHERE us.user_id = ? AND s.is_deleted = 0
  `;
  if (!includePrivate) sql += ' AND s.is_public = 1';
  sql += ' ORDER BY us.created_at DESC';
  return db.prepare(sql).all(userId);
}

export function subscribe(db, userId, sourceId) {
  return db.prepare('INSERT OR IGNORE INTO user_subscriptions (user_id, source_id) VALUES (?, ?)').run(userId, sourceId);
}

export function unsubscribe(db, userId, sourceId) {
  return db.prepare('DELETE FROM user_subscriptions WHERE user_id = ? AND source_id = ?').run(userId, sourceId);
}

export function bulkSubscribe(db, userId, sourceIds) {
  const stmt = db.prepare('INSERT OR IGNORE INTO user_subscriptions (user_id, source_id) VALUES (?, ?)');
  const run = db.transaction((ids) => {
    let added = 0;
    for (const sid of ids) {
      const r = stmt.run(userId, sid);
      added += r.changes;
    }
    return added;
  });
  return run(sourceIds);
}

export function isSubscribed(db, userId, sourceId) {
  return !!db.prepare('SELECT 1 FROM user_subscriptions WHERE user_id = ? AND source_id = ?').get(userId, sourceId);
}

export function getSubscriberCount(db, sourceId) {
  return db.prepare('SELECT COUNT(*) as count FROM user_subscriptions WHERE source_id = ?').get(sourceId).count;
}

// ── Feedback ──

export function createFeedback(db, userId, email, name, message, category) {
  const result = db.prepare('INSERT INTO feedback (user_id, email, name, message, category) VALUES (?, ?, ?, ?, ?)').run(userId, email, name, message, category || null);
  return result.lastInsertRowid;
}

export function getUserFeedback(db, userId) {
  return db.prepare('SELECT id, message, reply, replied_by, replied_at, created_at, status, category, read_at FROM feedback WHERE user_id = ? ORDER BY created_at DESC').all(userId);
}

export function getAllFeedback(db) {
  return db.prepare(`SELECT f.*, u.name as user_name, u.email as user_email, u.avatar as user_avatar
    FROM feedback f LEFT JOIN users u ON f.user_id = u.id ORDER BY f.created_at DESC`).all();
}

export function replyToFeedback(db, id, reply, repliedBy) {
  return db.prepare("UPDATE feedback SET reply = ?, replied_by = ?, replied_at = datetime('now'), status = 'replied' WHERE id = ?").run(reply, repliedBy, id);
}

export function updateFeedbackStatus(db, id, status) {
  return db.prepare("UPDATE feedback SET status = ? WHERE id = ?").run(status, id);
}

export function markFeedbackRead(db, id) {
  return db.prepare("UPDATE feedback SET read_at = datetime('now') WHERE id = ?").run(id);
}

export function getUnreadFeedbackCount(db, userId) {
  return db.prepare("SELECT COUNT(*) as count FROM feedback WHERE user_id = ? AND reply IS NOT NULL AND read_at IS NULL").get(userId)?.count || 0;
}

// ── Config ──

export function getConfig(db) {
  const rows = db.prepare('SELECT key, value FROM config').all();
  const obj = {};
  for (const r of rows) {
    try { obj[r.key] = JSON.parse(r.value); } catch { obj[r.key] = r.value; }
  }
  return obj;
}

export function setConfig(db, key, value) {
  const v = typeof value === 'string' ? value : JSON.stringify(value);
  db.prepare('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)').run(key, v);
}

// ── Source Groups ──

export function listSourceGroups(db, { activeOnly } = {}) {
  let sql = 'SELECT * FROM source_groups';
  const conditions = [];
  const params = [];
  if (activeOnly) { conditions.push('is_active = 1'); }
  if (conditions.length) sql += ' WHERE ' + conditions.join(' AND ');
  sql += ' ORDER BY created_at DESC';
  return db.prepare(sql).all(...params);
}

export function getSourceGroup(db, id) {
  return db.prepare('SELECT * FROM source_groups WHERE id = ?').get(id);
}

export function createSourceGroup(db, { name, description = '', digestTypes = '[]', timezone = 'UTC', schedule = '{}', telegram_thread_id = null, telegram_chat_id = null, prompt_id = null }) {
  const result = db.prepare(
    'INSERT INTO source_groups (name, description, digest_types, timezone, schedule, telegram_thread_id, telegram_chat_id, prompt_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
  ).run(name, description, digestTypes, timezone, schedule, telegram_thread_id, telegram_chat_id, prompt_id);
  return { id: result.lastInsertRowid };
}

export function updateSourceGroup(db, id, patch) {
  const allowed = ['name', 'description', 'digest_types', 'timezone', 'schedule', 'is_active', 'telegram_thread_id', 'telegram_chat_id', 'prompt_id'];
  const sets = [];
  const params = [];
  for (const [k, v] of Object.entries(patch)) {
    const col = k === 'isActive' ? 'is_active' : k === 'digestTypes' ? 'digest_types' : k;
    if (allowed.includes(col)) {
      sets.push(`${col} = ?`);
      params.push(typeof v === 'boolean' ? (v ? 1 : 0) : v);
    }
  }
  if (!sets.length) return { changes: 0 };
  sets.push("updated_at = datetime('now')");
  params.push(id);
  return db.prepare(`UPDATE source_groups SET ${sets.join(', ')} WHERE id = ?`).run(...params);
}

export function deleteSourceGroup(db, id) {
  // Unassign all sources from this group first
  db.prepare('UPDATE sources SET group_id = NULL WHERE group_id = ?').run(id);
  return db.prepare('DELETE FROM source_groups WHERE id = ?').run(id);
}

export function getSourceGroupByName(db, name) {
  return db.prepare('SELECT * FROM source_groups WHERE name = ?').get(name);
}

// ── Digest Prompts ──

function _seedPromptsFromFiles(db) {
  const count = db.prepare('SELECT COUNT(*) as c FROM digest_prompts').get();
  if (count.c > 0) return; // Already seeded
  const promptsDir = join(ROOT, 'templates', 'prompts');
  const defaultTemplate = join(ROOT, 'templates', 'digest-prompt.md');
  // Seed the default prompt
  if (existsSync(defaultTemplate)) {
    const content = readFileSync(defaultTemplate, 'utf8');
    db.prepare('INSERT INTO digest_prompts (name, content, is_default) VALUES (?, ?, 1)').run('Default', content);
  } else {
    db.prepare('INSERT INTO digest_prompts (name, content, is_default) VALUES (?, ?, 1)').run('Default',
      '# Default Digest Prompt\n\nYou are a tech news curator. Create a structured daily digest from the provided sources.\nFocus on AI research, prompt engineering, LLM management, hardware (ESP32), and modern dev stacks.\n\n{{recent_context}}\n\nFORMAT:\n☀️ ClawFeed | {{date}} {{timezone}}\n\n🔥 Important (2-3 truly significant items)\n• **[Headline]** — [2-3 sentence summary]\n\n📰 Feed Highlights ({{highlights_count}} items, diversified across sources)\n• **[Source Name]**: [Detailed summary]'
    );
  }
  // Seed group-specific prompts from files
  if (existsSync(promptsDir)) {
    try {
      const files = readdirSync(promptsDir);
      for (const file of files) {
        if (!file.endsWith('.md')) continue;
        const name = file.replace('.md', '').split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
        const content = readFileSync(join(promptsDir, file), 'utf8');
        try {
          db.prepare('INSERT INTO digest_prompts (name, content, is_default) VALUES (?, ?, 0)').run(name, content);
        } catch (e) { /* Ignore duplicates */ }
      }
    } catch (e) {
      console.error('Seed prompts:', e.message);
    }
  }
  // Auto-assign prompts to groups by name matching
  _autoAssignPrompts(db);
}

function _autoAssignPrompts(db) {
  const prompts = db.prepare('SELECT id, name FROM digest_prompts WHERE is_default = 0').all();
  const groups = db.prepare('SELECT id, name FROM source_groups WHERE prompt_id IS NULL').all();
  for (const group of groups) {
    const normalized = group.name.replace(/[^\w\s]/g, '').trim().toLowerCase().replace(/\s+/g, ' ');
    for (const prompt of prompts) {
      const promptNorm = prompt.name.toLowerCase().replace(/-/g, ' ');
      if (normalized === promptNorm || normalized.includes(promptNorm) || promptNorm.includes(normalized)) {
        db.prepare('UPDATE source_groups SET prompt_id = ? WHERE id = ?').run(prompt.id, group.id);
        break;
      }
    }
  }
}

export function listPrompts(db) {
  return db.prepare('SELECT * FROM digest_prompts ORDER BY is_default DESC, name ASC').all();
}

export function getPrompt(db, id) {
  return db.prepare('SELECT * FROM digest_prompts WHERE id = ?').get(id);
}

export function createPrompt(db, { name, content, is_default = 0 }) {
  const result = db.prepare(
    'INSERT INTO digest_prompts (name, content, is_default) VALUES (?, ?, ?)'
  ).run(name, content, is_default);
  return { id: result.lastInsertRowid };
}

export function updatePrompt(db, id, { name, content }) {
  const sets = [];
  const params = [];
  if (name !== undefined) { sets.push('name = ?'); params.push(name); }
  if (content !== undefined) { sets.push('content = ?'); params.push(content); }
  if (!sets.length) return { changes: 0 };
  sets.push("updated_at = datetime('now')");
  params.push(id);
  return db.prepare(`UPDATE digest_prompts SET ${sets.join(', ')} WHERE id = ?`).run(...params);
}

export function deletePrompt(db, id) {
  // Guard: cannot delete default prompt
  const prompt = db.prepare('SELECT is_default FROM digest_prompts WHERE id = ?').get(id);
  if (!prompt) return { error: 'not found' };
  if (prompt.is_default) return { error: 'cannot delete default prompt' };
  // Unassign groups using this prompt
  db.prepare('UPDATE source_groups SET prompt_id = NULL WHERE prompt_id = ?').run(id);
  return db.prepare('DELETE FROM digest_prompts WHERE id = ?').run(id);
}

export function getPromptForGroup(db, groupId) {
  const row = db.prepare(
    'SELECT dp.* FROM digest_prompts dp JOIN source_groups sg ON sg.prompt_id = dp.id WHERE sg.id = ?'
  ).get(groupId);
  if (row) return row;
  // Fall back to default prompt
  return db.prepare('SELECT * FROM digest_prompts WHERE is_default = 1').get();
}

// ── Settings ──

export function getSetting(db, key) {
  const row = db.prepare('SELECT value FROM settings WHERE key = ?').get(key);
  if (!row) return null;
  try { return JSON.parse(row.value); } catch { return row.value; }
}

export function setSetting(db, key, value) {
  const v = typeof value === 'string' ? value : JSON.stringify(value);
  db.prepare("INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now'))").run(key, v);
}

export function getAllSettings(db) {
  const rows = db.prepare('SELECT key, value FROM settings').all();
  const obj = {};
  for (const r of rows) {
    try { obj[r.key] = JSON.parse(r.value); } catch { obj[r.key] = r.value; }
  }
  return obj;
}
