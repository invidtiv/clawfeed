# ClawFeed

> **Stop scrolling. Start knowing.**

[![ClawHub](https://img.shields.io/badge/ClawHub-clawfeed-blue)](https://clawhub.ai/skills/clawfeed)
[![GitHub](https://img.shields.io/github/v/tag/kevinho/clawfeed?label=version)](https://github.com/kevinho/clawfeed)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live Demo: https://clawfeed.kevinhe.io](https://clawfeed.kevinhe.io)

AI-powered news digest that curates thousands of sources down to the highlights that matter. Generates structured summaries (4H/daily/weekly/monthly) from Twitter, RSS, and more. Works standalone or as an [OpenClaw](https://github.com/openclaw/openclaw) / [Zylos](https://github.com/zylos-ai) skill.

![Dashboard](docs/demo.gif)

## Features

- 📰 **Multi-frequency digests** — 4-hourly, daily, weekly, monthly summaries
- 🏷️ **Source Groups** — Organize sources into groups with separate digests per group
- 📡 **Sources system** — Add Twitter feeds, RSS, HackerNews, Reddit, GitHub Trending, and more
- 📦 **Source Packs** — Share curated source bundles with the community
- 📌 **Mark & Deep Dive** — Bookmark content for AI-powered deep analysis
- 🎯 **Smart curation** — Configurable rules for content filtering and noise reduction
- 👀 **Follow/Unfollow suggestions** — Based on feed quality analysis
- 📢 **Feed output** — Subscribe to any user's digest via RSS or JSON Feed
- 🌐 **Multi-language** — English and Chinese UI
- 🌙 **Dark/Light mode** — Theme toggle with localStorage persistence
- ⚙️ **Settings** — Configure global timezone and UI language preferences
- 🖥️ **Web dashboard** — SPA for browsing and managing digests
- 💾 **SQLite storage** — Fast, portable, zero-config database
- 🔐 **Google OAuth** — Multi-user support with personal bookmarks and sources

## Installation

### Option 1: ClawHub (recommended)

```bash
clawhub install clawfeed
```

### Option 2: OpenClaw Skill

```bash
cd ~/.openclaw/skills/
git clone https://github.com/kevinho/clawfeed.git
```

OpenClaw auto-detects `SKILL.md` and loads the skill. The agent can then generate digests via cron, serve the dashboard, and handle bookmark commands.

### Option 3: Zylos Skill

```bash
cd ~/.zylos/skills/
git clone https://github.com/kevinho/clawfeed.git
```

### Option 4: Standalone

```bash
git clone https://github.com/kevinho/clawfeed.git
cd clawfeed
npm install
```

### Option 5: Docker
```bash
# Basic usage
docker run -d -p 8767:8767 kevinho/clawfeed

# With persistent data
docker run -d -p 8767:8767 -v clawfeed-data:/app/data kevinho/clawfeed

# With environment variables (recommended for production)
docker run -d -p 8767:8767 \
  -v clawfeed-data:/app/data \
  -e ALLOWED_ORIGINS=https://yourdomain.com \
  -e API_KEY=your-api-key \
  -e GOOGLE_CLIENT_ID=your-client-id \
  -e GOOGLE_CLIENT_SECRET=your-client-secret \
  -e SESSION_SECRET=your-session-secret \
  kevinho/clawfeed
```

## Quick Start

```bash
# 1. Copy and edit environment config
cp .env.example .env
# Edit .env with your settings

# 2. Start the API server
npm start
# → API running on http://0.0.0.0:8767
# → Accessible via Tailscale at http://YOUR-TAILSCALE-HOSTNAME:8767
```

## Tailscale Access

ClawFeed is configured to be accessible via Tailscale by default:

1. **Server binds to all interfaces** (`0.0.0.0`) to accept connections from Tailscale
2. **CORS allows `*.ts.net`** domains by default
3. **Access your instance** at `http://YOUR-TAILSCALE-HOSTNAME:8767`

To restrict to localhost only, set `DIGEST_HOST=127.0.0.1` in your `.env` file.

## Environment Variables

Create a `.env` file in the project root:

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | No* | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth client secret | No* | - |
| `SESSION_SECRET` | Session encryption key | No* | - |
| `GOOGLE_API_KEY` | Gemini API key for AI digest summarization | No | - |
| `GEMINI_API_KEY` | Alternative Gemini key variable name | No | - |
| `API_KEY` | API key for digest creation | No | - |
| `DIGEST_PORT` | Server port | No | 8767 |
| `DIGEST_HOST` | Bind address (0.0.0.0 for all interfaces, 127.0.0.1 for localhost only) | No | 0.0.0.0 |
| `ALLOWED_ORIGINS` | Allowed origins for CORS | No | localhost,*.ts.net |

\*Required for authentication features. Without OAuth, the app runs in read-only mode.

## Authentication Setup

To enable Google OAuth login:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Google+ API
4. Create OAuth 2.0 credentials
5. Add your domain to authorized origins
6. Add callback URL: `https://yourdomain.com/api/auth/callback`
7. Set credentials in `.env`

## API

All endpoints prefixed with `/api/`.

### Digests

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/digests` | List digests `?type=4h&limit=20&offset=0` | - |
| `GET` | `/api/digests/:id` | Get single digest | - |
| `POST` | `/api/digests` | Create digest | API Key |

### Auth

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/auth/config` | Auth availability check | - |
| `GET` | `/api/auth/google` | Start OAuth flow | - |
| `GET` | `/api/auth/callback` | OAuth callback | - |
| `GET` | `/api/auth/me` | Current user info | Yes |
| `POST` | `/api/auth/logout` | Logout | Yes |

### Marks (Bookmarks)

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/marks` | List bookmarks | Yes |
| `POST` | `/api/marks` | Add bookmark `{ url, title?, note? }` | Yes |
| `DELETE` | `/api/marks/:id` | Remove bookmark | Yes |

### Source Groups

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/groups` | List all source groups | - |
| `GET` | `/api/groups/:id` | Get single group | - |
| `POST` | `/api/groups` | Create group `{ name, description?, digestTypes?, timezone?, schedule? }` | - |
| `PUT` | `/api/groups/:id` | Update group | - |
| `DELETE` | `/api/groups/:id` | Delete group (unassigns sources first) | - |

### Settings

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/settings` | Get all settings | - |
| `GET` | `/api/settings/:key` | Get single setting | - |
| `PUT` | `/api/settings` | Update settings `{ global_timezone?, default_language? }` | - |
| `PUT` | `/api/settings/:key` | Update single setting | - |

### Sources

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/sources` | List sources (logged in: own + public, guest: public only) | Optional |
| `POST` | `/api/sources` | Create source `{ name, type, config }` | Yes |
| `PUT` | `/api/sources/:id` | Update source | Yes |
| `DELETE` | `/api/sources/:id` | Soft-delete source | Yes |
| `POST` | `/api/sources/resolve` | Auto-detect source from URL `{ url }` | Yes |

### Subscriptions

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/subscriptions` | List current user's subscribed sources | Yes |
| `POST` | `/api/subscriptions` | Subscribe to source `{ sourceId }` | Yes |
| `POST` | `/api/subscriptions/bulk` | Subscribe in batch `{ sourceIds: [] }` | Yes |
| `DELETE` | `/api/subscriptions/:sourceId` | Unsubscribe source | Yes |

### Public User Selections

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/users/:slug/sources` | List a user's selected sources (public only; self gets full list) | Optional |

### Source Packs

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/packs` | Browse public packs | - |
| `POST` | `/api/packs` | Create pack from your sources | Yes |
| `POST` | `/api/packs/:slug/install` | Install pack (subscribe to its sources) | Yes |

### Feeds

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/feed/:slug` | User's digest feed (HTML) | - |
| `GET` | `/feed/:slug.json` | JSON Feed format | - |
| `GET` | `/feed/:slug.rss` | RSS format | - |

### Config

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/changelog` | Changelog `?lang=zh\|en` | - |
| `GET` | `/api/roadmap` | Roadmap `?lang=zh\|en` | - |

## Reverse Proxy

Example Caddy configuration:

```caddyfile
handle /digest/api/* {
    uri strip_prefix /digest/api
    reverse_proxy localhost:8767
}
handle_path /digest/* {
    root * /path/to/clawfeed/web
    file_server
}
```

## Group-Based Digest Generation

Organize your sources into groups and generate separate digests for each group automatically:

### Creating Groups

Use the web UI (Settings → Groups tab) or API:

```bash
curl -X POST http://127.0.0.1:8767/api/groups \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Tech News",
    "description": "Technology and AI updates",
    "digestTypes": ["4h-tech", "daily-tech"],
    "timezone": "America/Los_Angeles"
  }'
```

### Generating Digests

Run a single command to generate digests for **all groups** automatically:

```bash
python3 generate-digest.py 4h-tech
```

The system will:
1. Load all sources and groups from the database
2. Partition sources by `group_id`
3. Generate separate digests for each group
4. Handle ungrouped sources as a "General" digest
5. Store each digest with its `group_id` for filtering

**Example output:**
```
📚 Loaded 39 sources
🏷️  Loaded 3 active groups
📊 Grouping summary:
   - 3 groups with sources
   - 4 ungrouped sources

============================================================
🔄 Processing group: Tech News
============================================================
✅ Sources with usable content: 15/15
✅ Digest created! ID: 47

============================================================
📋 Final Summary
============================================================
✅ Successfully generated: 3 digests
✅ Tech News: http://127.0.0.1:8767/#digest-47
✅ Status Updates: http://127.0.0.1:8767/#digest-48
✅ General (ungrouped): http://127.0.0.1:8767/#digest-49
```

### Custom Digest Types

You can use any digest type naming convention (e.g., `4h-tech`, `daily-status`, `weekly-pt`). The system automatically handles custom types without constraints.

## Customization

- **Curation rules**: Edit `templates/curation-rules.md` to control content filtering
- **Digest format**: Edit `templates/digest-prompt.md` to customize AI output format
- **Local sources bootstrap**: When `config.json` contains a `sources` array, the API auto-syncs them into the Sources page on server start (including `enabled` and `digestTypes` metadata)

## Source Types

| Type | Example | Description |
|------|---------|-------------|
| `twitter_feed` | `@karpathy` | Twitter/X user feed |
| `twitter_list` | List URL | Twitter list |
| `rss` | Any RSS/Atom URL | RSS feed |
| `hackernews` | HN Front Page | Hacker News |
| `reddit` | `/r/MachineLearning` | Subreddit |
| `github_trending` | `language=python` | GitHub trending repos |
| `website` | Any URL | Website scraping |
| `digest_feed` | ClawFeed user slug | Another user's digest |
| `custom_api` | JSON endpoint | Custom API |

## Development

```bash
npm run dev  # Start with --watch for auto-reload
```

### Testing

```bash
cd test
./setup.sh    # Create test users
./e2e.sh      # Run 66 E2E tests
./teardown.sh # Clean up
```

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for multi-tenant design and scale analysis.

## Roadmap

See [ROADMAP.md](ROADMAP.md) or the in-app roadmap page.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright 2026 Kevin He
