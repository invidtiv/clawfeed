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
# Create a group via API
curl -X POST http://127.0.0.1:8767/api/groups \
  -H "Content-Type: application/json" \
  -d '{"name":"Tech News","digestTypes":["4h-tech"]}'

# Generate digests for all groups in one command
python3 generate-digest.py 4h-tech
```

The system automatically:
- Loads all sources and groups
- Partitions sources by group
- Generates separate digests per group
- Handles ungrouped sources as "General"
- Stores each digest with its `group_id`

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
