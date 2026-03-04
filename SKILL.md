# ClawFeed

AI-powered news digest tool. Automatically generates structured summaries (4H/daily/weekly/monthly) from Twitter and RSS feeds.

## Credentials & Dependencies

ClawFeed runs in **read-only mode** with zero credentials — browse digests, view feeds, switch languages. Authentication features (bookmarks, sources, packs) require additional credentials.

| Credential | Purpose | Required |
|-----------|---------|----------|
| `GOOGLE_CLIENT_ID` | Google OAuth login | For auth features |
| `GOOGLE_CLIENT_SECRET` | Google OAuth login | For auth features |
| `SESSION_SECRET` | Session cookie encryption | For auth features |
| `API_KEY` | Digest creation endpoint protection | For write API |

**Runtime dependency:** SQLite via `better-sqlite3` (native addon, bundled). No external database server required.

## Setup

```bash
# Install dependencies
npm install

# Copy environment config
cp .env.example .env
# Edit .env with your settings

# Start API server
npm start
```

## Environment Variables

Configure in `.env` file:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `DIGEST_PORT` | Server port | No | 8767 |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | For auth | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | For auth | - |
| `SESSION_SECRET` | Session cookie encryption key | For auth | - |
| `GOOGLE_API_KEY` | Gemini API key for digest summarization | For AI summaries | - |
| `GEMINI_API_KEY` | Alternative Gemini API key variable name | For AI summaries | - |
| `API_KEY` | Digest creation API key | For write API | - |
| `AI_DIGEST_DB` | SQLite database path | No | `data/digest.db` |
| `ALLOWED_ORIGINS` | CORS allowed origins | No | localhost |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token for autonomous posting | For Telegram | - |
| `TELEGRAM_CHAT_ID` | Telegram supergroup chat ID (default for all groups) | For Telegram | - |

## API Server

Runs on port `8767` by default. Set `DIGEST_PORT` env to change.

### Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | /api/digests | List digests (?type=4h\|daily\|weekly&limit=20&offset=0) | - |
| GET | /api/digests/:id | Get single digest | - |
| POST | /api/digests | Create digest (internal) | API Key |
| GET | /api/groups | List source groups | - |
| POST | /api/groups | Create source group | - |
| PUT | /api/groups/:id | Update source group | - |
| DELETE | /api/groups/:id | Delete source group | - |
| GET | /api/settings | Get all settings | - |
| PUT | /api/settings | Update settings | - |
| GET | /api/auth/google | Start Google OAuth flow | - |
| GET | /api/auth/callback | OAuth callback endpoint | - |
| GET | /api/auth/me | Get current user info | Yes |
| POST | /api/auth/logout | Logout user | Yes |
| GET | /api/marks | List user bookmarks | Yes |
| POST | /api/marks | Add bookmark | Yes |
| DELETE | /api/marks/:id | Remove bookmark | Yes |
| GET | /api/config | Get configuration | - |
| PUT | /api/config | Update configuration | - |

## Web Dashboard

Serve `web/index.html` via your reverse proxy or any static file server.

**Features:**
- Browse digests with dark/light mode toggle
- **Groups tab** — Organize sources into groups with separate digests
- **Settings tab** — Configure global timezone and UI language
- Multi-language support (English/Chinese)
- Bookmark content for deep analysis

## Group-Based Digest Generation

Organize sources into groups and generate separate digests automatically:

```bash
# Generate digests for all groups matching a type
python3 generate-digest.py 4h-tech

# Generate for a single group only
python3 generate-digest.py 4h-pt --group-id=3

# Generate and immediately post to Telegram
python3 generate-digest.py daily --post-telegram

# Both flags together (typical autonomous use)
python3 generate-digest.py 4h-pt --post-telegram --group-id=3
```

The system automatically:
- Loads all sources and groups from the DB
- Partitions sources by group
- Generates separate digests per group
- Handles ungrouped sources as "General"
- Stores each digest with its `group_id`
- Posts to each group's configured Telegram thread (when `--post-telegram` is set)

## Autonomous Scheduling

The Node.js server includes a built-in 60-second scheduler that fires `generate-digest.py` per group based on the `schedule` JSON field stored in `source_groups`.

**Schedule format:**
```json
{"at": ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00"]}
{"at": ["08:00"], "on": "Monday"}
{"at": ["09:00"], "on": "weekday"}
```

Times are evaluated in the group's `timezone`. Configure schedules and Telegram thread IDs via the **Groups** tab in the web dashboard.

**systemd service** (user-level, auto-starts on login):
```bash
systemctl --user status clawfeed
systemctl --user restart clawfeed
journalctl --user -u clawfeed -f
```

## Telegram Setup

1. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env`
2. In the web dashboard **Groups** tab, edit each group and set its **Telegram Thread ID** (the topic/thread ID within the supergroup)
3. Test manually: `python3 generate-digest.py daily --post-telegram --group-id=<id>`
4. The Node server scheduler handles the rest — no cron jobs needed

## Templates

- `templates/curation-rules.md` — Customize feed curation rules
- `templates/digest-prompt.md` — Customize the AI summarization prompt

## Configuration

Copy `config.example.json` to `config.json` and edit. See README for details.

## Reverse Proxy (Caddy example)

```
handle /digest/api/* {
    uri strip_prefix /digest/api
    reverse_proxy localhost:8767
}
handle_path /digest/* {
    root * /path/to/clawfeed/web
    file_server
}
```
