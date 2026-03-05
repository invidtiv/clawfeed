# Changelog

## v0.9.2 — 2026-03-05
### ✨ New
- **Digest deduplication** — Two-layer system prevents repeating the same stories across consecutive digests:
  - **URL-level filter (pre-AI)**: Items already included in a recent digest for the same group are removed before the AI prompt is built. Windows: 4h→8h, daily→26h, weekly→8d, monthly→32d
  - **Semantic context (in-AI)**: Recent item titles are injected into the prompt as a "RECENTLY COVERED" block, instructing the AI to skip overlapping stories or mark genuine follow-ups as `🔄 Update:`
- **`digest_items` table** — New DB table tracks every feed item URL and title per digest, keyed by `group_id` and timestamp
- **Timezone display fix** — Digest card timestamps now shown in the `global_timezone` from settings (default `Europe/Lisbon`) instead of hardcoded SGT (+08:00)
  - `parseCreatedAt` treats DB timestamps as UTC (`Z`) instead of Singapore time
  - `appTimezone` loaded from `GET /api/settings` at page startup before first render
  - Card times use `toLocaleTimeString` with correct `timeZone` option; "SGT" label removed

### 🔧 Database
- **Migration 013** — New `digest_items (id, digest_id, group_id, item_url, item_title, created_at)` table with index on `(group_id, created_at)` for fast recent-item lookups
- Python script self-creates `digest_items` table if migration 013 hasn't run via Node yet

### 🔧 Internal
- `generate-digest.py`: added `load_seen_items()`, `save_digest_items()`, `_extract_item_url()`, `_ensure_digest_items_table()`, `DEDUP_WINDOW_HOURS` dict
- `templates/digest-prompt.md`: added `{{recent_context}}` placeholder and dedup instructions
- `web/index.html`: `appTimezone` global; startup settings fetch; UTC parsing in `parseCreatedAt`; timezone-aware weekday/date display

---

## v0.9.1 — 2026-03-05
### ✨ New
- **Autonomous Telegram posting** — Digests are posted directly to Telegram immediately after generation, with no manual step required
  - Each source group can have a dedicated `telegram_thread_id` (topic thread) and optional `telegram_chat_id` override
  - Configurable via the Groups UI — Thread ID and Chat ID fields added to the group form
  - Uses the bot token from `.env` (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
  - Groups without a thread ID configured are silently skipped
- **Built-in scheduler** — Node.js server now runs digest generation autonomously on each group's configured schedule
  - 60-second tick reads all active groups from the DB and fires `generate-digest.py` when the current time matches the group's `schedule.at` times
  - Fully timezone-aware via `Intl.DateTimeFormat` with per-group `timezone`
  - Supports `"on": "weekday"` / `"on": "weekend"` / `"on": "Monday"` modifiers
  - Deduplication prevents double-firing within the same minute
- **`--post-telegram` flag** — `generate-digest.py` can now post to Telegram inline: `python3 generate-digest.py 4h-pt --post-telegram`
- **`--group-id=N` flag** — Run digest generation for a single group only: `python3 generate-digest.py daily --group-id=3`
- **Group schedule UI** — Schedule JSON field added to the group form (e.g. `{"at":["08:00","20:00"]}`)
- **Group card badges** — Thread ID and scheduled times now visible on group cards in the Groups tab
- **systemd service** — `clawfeed.service` user systemd unit created at `~/.config/systemd/user/clawfeed.service` for auto-start on login with restart-on-failure

### 🔧 Database
- **Migration 012** — Added `telegram_thread_id INTEGER` and `telegram_chat_id TEXT` columns to `source_groups`; added global `telegram_bot_token` and `telegram_chat_id` keys to `settings`
- Python script self-applies migration 012 DDL at startup if columns are missing (no dependency on Node server having run first)

### 🌐 API
- `PUT /api/groups/:id` now accepts and persists `telegram_thread_id` and `telegram_chat_id`
- `POST /api/groups` now accepts `telegram_thread_id` and `telegram_chat_id` on creation
- `GET /api/groups` and `GET /api/groups/:id` return the new Telegram fields

### 🔧 Internal
- Telegram sending functions (`send_message`, `split_content`, `post_digest_to_topic`) consolidated into `generate-digest.py` — `post-to-telegram.py` retained for manual/emergency use
- `src/server.mjs` imports `child_process.spawn` to manage scheduled Python subprocess invocations
- Telegram credentials moved from hardcoded values in `post-to-telegram.py` to `.env`

## v0.9.0 — 2026-03-04
### ✨ New
- **Source Groups** — Organize sources into groups with separate digests per group (#TBD)
  - New `source_groups` table with `digestTypes`, `timezone`, and `schedule` per group
  - Sources can be assigned to groups via `group_id` column
  - Groups management UI in web dashboard (Groups tab)
- **Global Settings** — Configure system-wide preferences (#TBD)
  - New `settings` table for global configuration
  - Settings UI for timezone and language preferences
  - API endpoints: `GET/PUT /api/settings`
- **Group-Based Digest Generation** — Single command generates digests for all groups automatically (#TBD)
  - `python3 generate-digest.py 4h-tech` now loads all sources, partitions by group, and generates separate digests
  - Each digest stored with `group_id` for filtering and organization
  - Ungrouped sources handled as "General" digest
  - Detailed progress reporting per group
- **Custom Digest Types** — Removed CHECK constraint to allow any digest type naming (e.g., `4h-tech`, `daily-status`, `weekly-pt`) (#TBD)

### 🔧 Database
- **Migration 010** — Added `source_groups` and `settings` tables, `group_id` columns to `sources` and `digests`
- **Migration 011** — Removed digest type constraint to support custom types

### 🌐 API
- `GET /api/groups` — List all source groups
- `POST /api/groups` — Create source group
- `PUT /api/groups/:id` — Update source group
- `DELETE /api/groups/:id` — Delete source group (unassigns sources first)
- `GET /api/settings` — Get all settings
- `PUT /api/settings` — Update settings
- Updated `POST /api/digests` to accept and store `group_id`

### 📖 Documentation
- Updated README.md with Group-Based Digest Generation section
- Updated SKILL.md with groups and settings endpoints
- Added comprehensive API documentation for new endpoints

## v0.8.1 — 2026-02-24
### ✨ New
- **Telegram group link in info banner** — Clickable TG icon + group invite link with i18n support (#16)
- **DEVOPLOG.md** — R&D lifecycle tracking for staging/production changes (#20)

### 🔧 Fixed
- **TG icon rendering** — Replace emoji with proper SVG icon, make TG group link clickable (#17)
- **Subtitle Twitter links** — @mentions in subtitle now link to Twitter profiles (#18)
- **ClawHub metadata alignment** — SKILL.md credentials declared, TESTING.md HttpOnly note, README/SKILL.md consistency (#25)

### 🏗️ Infrastructure
- **CI pipeline** — GitHub Actions for lint + security audit on PRs (#2, #9)
- **PR template & CONTRIBUTING.md** — Standardized contribution workflow (#3)
- **Health endpoint** — `GET /api/health` for CI readiness checks (#4)
- **Feedback webhook config** — `FEEDBACK_LARK_WEBHOOK` in .env.example (#5)
- **Dev process docs** — Full PROCESS.md workflow (#7)
- **Security hardening** — SSRF protection, OAuth state validation, API key handling (#1)

## v0.7.0 — 2026-02-22
### ✨ New
- **Dark/Light mode toggle** — Sun/moon toggle in header, persists in localStorage
- **Video demo in README** — Uploaded demo.mp4 as GitHub release asset for proper embedding

### 🔧 Fixed
- README video now auto-plays on GitHub (release asset URL instead of relative path)

## v0.6.0 — 2026-02-22
### ✨ New
- **Soft Delete Sources** — Sources marked `is_deleted` instead of hard delete; prevents pack zombie resurrection
- **Roadmap page** — Accessible from ⋯ More menu
- **Test documentation** — Full test case index with iteration log

### 🔧 Fixed
- Pack install skips deleted sources (no more zombie duplicates)
- Subscription list shows deactivated sources (greyed out + ⚠️ badge)

## v0.5.0 — 2026-02-21
### ✨ New
- **Digest Feed System** — Each user gets a subscribable feed (`/feed/:slug.json`, `/feed/:slug.rss`, `/feed/:slug`)
- **Smart Source Detection** — Paste any URL, auto-detect source type (RSS, Twitter, HN, Reddit, etc.)
- **Sources Management** — ⚙️ UI to add/edit/delete data sources with type-specific config examples
- **Auth Config API** — Hide login UI when Google OAuth not configured (for third-party deployments)
- **API Key Auth** — `POST /api/digests` uses Bearer token authentication

### 🔧 Fixed
- Tab switching state reset when navigating from Sources
- Timezone grouping bug (UTC vs local date)
- Title click returns to home

### 🗑️ Removed
- Admin role system (every user manages own data)

## v0.4.0 — 2026-02-21
### ✨ New
- **i18n** — Chinese/English toggle with localStorage persistence
- **Google OAuth** — Sign in with Google, session cookies, per-user marks
- **Private sections** — 🧹建议取关 and 🔖Bookmarks hidden for non-logged-in users
- **Open source** — Published to GitHub under MIT license

### 🔧 Fixed
- Header layout flex (no more position:absolute overlap)
- Auth timing race condition (checkAuth before renderList)
- Mobile responsive title

## v0.3.0 — 2026-02-21
### ✨ New
- **SQLite storage** — Migrated from markdown files to better-sqlite3
- **Marks system** — Bookmark articles with dedup, per-user isolation
- **Dashboard pagination** — 10 items per page with "Load more"
- **Excerpt preview** — 1-2 line preview for digest cards
- **Time grouping** — 4H→day, daily→week, weekly→month, monthly→year

## v0.2.0 — 2026-02-21
### ✨ New
- **Standalone server** — Node HTTP server on port 8767
- **REST API** — GET/POST digests, GET/POST/DELETE marks
- **Dashboard** — Dark theme, tabs for 4H/Daily/Weekly/Monthly/Marks
- **Domain** — digest.kevinhe.io with Cloudflare Access

## v0.1.0 — 2026-02-21
### ✨ New
- **Initial release** — ClawFeed with web dashboard, Google OAuth, SQLite storage
- **4H cron** — Every 4 hours digest from Twitter For You feed
- **Daily/Weekly/Monthly** — Recursive summarization pipeline
