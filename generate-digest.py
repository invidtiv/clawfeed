#!/usr/bin/env python3
"""
ClawFeed Digest Generator.

Source loading priority:
1) SQLite sources table (what the UI edits)
2) config.json fallback
"""

import os
import sys
import json
import sqlite3
import urllib.request
import urllib.error
import urllib.parse
import re
from html import unescape
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

def load_env_file(env_path):
    """Load simple KEY=VALUE entries from .env into process env (without overriding existing vars)."""
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        if '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

ROOT = Path(__file__).resolve().parent
load_env_file(ROOT / ".env")

# Config
API_KEY = os.environ.get("API_KEY", "0221f247a74a6ae5776b87e4a224d326cd22430be3a9c9087fe9d08f06771143")
API_URL = os.environ.get("API_URL", "http://127.0.0.1:8767/api/digests")
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
DB_PATH = Path(os.environ.get("DIGEST_DB") or os.environ.get("AI_DIGEST_DB") or (ROOT / "data" / "digest.db"))
LAST_GEMINI_ERROR = ""

ALLOWED_DIGEST_TYPES = {"4h", "4h-tech", "4h-status", "4h-pt", "daily", "weekly", "monthly"}


def normalize_digest_types(raw):
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ["daily"]
    cleaned = [str(x).strip() for x in raw if str(x).strip() in ALLOWED_DIGEST_TYPES]
    return cleaned or ["daily"]


def parse_source_config(cfg):
    if isinstance(cfg, dict):
        return dict(cfg)
    if isinstance(cfg, str) and cfg.strip():
        try:
            return json.loads(cfg)
        except Exception:
            return {}
    return {}


def canonical_url(url):
    if not url:
        return ""
    try:
        parsed = urllib.parse.urlparse(str(url).strip())
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return urllib.parse.urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))
    except Exception:
        return str(url).strip().rstrip("/")


def _xml_local_name(tag):
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _extract_feed_items(xml_content, limit=10):
    """Parse RSS/Atom content with XML parser, fallback to regex if malformed."""
    items = []
    try:
        root = ET.fromstring(xml_content)
        entries = root.findall(".//{*}item") + root.findall(".//{*}entry")
        for entry in entries[:limit]:
            title = ""
            link = ""
            for child in list(entry):
                cname = _xml_local_name(child.tag).lower()
                if cname == "title" and not title:
                    title = (child.text or "").strip()
                elif cname == "link" and not link:
                    href = child.attrib.get("href")
                    if href:
                        link = href.strip()
                    else:
                        link = (child.text or "").strip()
            title = re.sub(r"\s+", " ", unescape(title or "(untitled)")).strip()
            if title:
                items.append(f"• RSS: {title} ({link})")
        if items:
            return items
    except Exception:
        pass

    # Legacy regex fallback for partially malformed feeds.
    blocks = re.findall(r"<(?:item|entry)[^>]*>(.*?)</(?:item|entry)>", xml_content, re.DOTALL | re.IGNORECASE)
    for block in blocks[:limit]:
        title_match = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", block, re.DOTALL | re.IGNORECASE)
        link_match = re.search(r"<link[^>]*href=[\"']([^\"']+)[\"']", block, re.IGNORECASE)
        if not link_match:
            link_match = re.search(r"<link[^>]*>(.*?)</link>", block, re.DOTALL | re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else "(untitled)"
        link = link_match.group(1).strip() if link_match else ""
        title = re.sub(r"\s+", " ", unescape(title)).strip()
        items.append(f"• RSS: {title} ({link})")
    return items


def _rss_fallback_candidates(url):
    """Known fallback feed URLs for domains that frequently rotate feed endpoints."""
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.lower()
    base = f"{parsed.scheme or 'https'}://{host}" if host else ""
    candidates = []

    if "openai.com" in host:
        candidates.extend([
            "https://openai.com/news/rss.xml",
            "https://openai.com/blog/rss.xml",
        ])
    if "vercel.com" in host:
        candidates.extend(["https://vercel.com/atom"])
    if "supabase.com" in host:
        candidates.extend([
            "https://supabase.com/rss.xml",
            "https://supabase.com/feed.xml",
        ])
    if "ai.googleblog.com" in host or "blog.google" in host or "blogspot." in host:
        candidates.extend([
            "https://blog.google/technology/ai/rss/",
            "https://blog.google/rss/",
        ])

    if base:
        candidates.extend([f"{base}/rss.xml", f"{base}/feed.xml", f"{base}/atom"])

    unique = []
    seen = set()
    for cand in candidates:
        c = canonical_url(cand)
        if c and c != canonical_url(url) and c not in seen:
            seen.add(c)
            unique.append(cand)
    return unique


def _fetch_arxiv_api_from_rss_url(url, limit=10):
    """Fallback for arXiv RSS categories that currently return empty channels."""
    m = re.search(r"/rss/([A-Za-z0-9_.-]+)", str(url))
    if not m:
        return []
    category = m.group(1)
    api_url = (
        "https://export.arxiv.org/api/query?"
        + urllib.parse.urlencode(
            {
                "search_query": f"cat:{category}",
                "sortBy": "submittedDate",
                "sortOrder": "descending",
                "max_results": int(limit or 10),
            }
        )
    )
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (ClawFeed Bot)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
        return _extract_feed_items(content, limit=limit)
    except Exception:
        return []


def source_key(source):
    stype = source.get("type", "")
    cfg = parse_source_config(source.get("config"))
    if stype in ("rss", "digest_feed", "website", "custom_api"):
        return f"{stype}|{canonical_url(cfg.get('url'))}"
    if stype == "reddit":
        sub = str(cfg.get("subreddit", "")).strip().lower().lstrip("/")
        if sub.startswith("r/"):
            sub = sub[2:]
        return f"{stype}|{sub}"
    if stype == "twitter_feed":
        h = str(cfg.get("handle", "")).strip().lower().lstrip("@")
        return f"{stype}|{h}"
    if stype == "twitter_list":
        return f"{stype}|{canonical_url(cfg.get('list_url'))}"
    if stype == "github_trending":
        lang = str(cfg.get("language", "all")).strip().lower() or "all"
        since = str(cfg.get("since", "daily")).strip().lower() or "daily"
        return f"{stype}|{lang}|{since}"
    if stype == "hackernews":
        return "hackernews|default"
    try:
        cfg_s = json.dumps(cfg, sort_keys=True, separators=(",", ":"))
        return f"{stype}|{cfg_s}"
    except Exception:
        return f"{stype}|{cfg}"


def normalize_source(raw_source, origin):
    cfg = parse_source_config(raw_source.get("config"))
    raw_dts = raw_source.get("digestTypes")
    if not raw_dts:
        raw_dts = cfg.get("_digestTypes") or cfg.get("digestTypes")
    digest_types = normalize_digest_types(raw_dts)
    enabled = raw_source.get("enabled")
    if enabled is None:
        enabled = raw_source.get("is_active", True)
    return {
        "id": raw_source.get("id"),
        "name": raw_source.get("name", "(unnamed)"),
        "type": raw_source.get("type", ""),
        "config": cfg,
        "enabled": bool(enabled),
        "digestTypes": digest_types,
        "origin": origin,
        "group_id": raw_source.get("group_id"),  # Preserve group_id from database
    }


def load_sources_from_db():
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, name, type, config, is_active, group_id
            FROM sources
            WHERE is_deleted = 0
            ORDER BY id ASC
            """
        ).fetchall()
        return [normalize_source(dict(r), "db") for r in rows]
    except Exception as e:
        print(f"⚠️ Failed loading DB sources: {e}")
        return []
    finally:
        conn.close()


def load_groups_from_db():
    """Load source groups from database."""
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT id, name, description, digest_types, timezone, is_active
            FROM source_groups
            WHERE is_active = 1
            ORDER BY id ASC
            """
        ).fetchall()
        groups = {}
        for r in rows:
            gid = r['id']
            groups[gid] = {
                'id': gid,
                'name': r['name'],
                'description': r['description'],
                'digest_types': json.loads(r['digest_types'] or '[]'),
                'timezone': r['timezone'] or 'UTC'
            }
        return groups
    except Exception as e:
        print(f"⚠️ Failed loading groups from DB: {e}")
        return {}
    finally:
        conn.close()


def load_sources_from_config():
    config_path = ROOT / "config.json"
    if not config_path.exists():
        return []
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        sources = data.get("sources", [])
        if not isinstance(sources, list):
            return []
        return [normalize_source(s, "config") for s in sources if isinstance(s, dict)]
    except Exception as e:
        print(f"⚠️ Failed loading config.json sources: {e}")
        return []


def load_sources():
    db_sources = load_sources_from_db()
    cfg_sources = load_sources_from_config()
    merged = []
    seen = set()
    for s in db_sources:
        k = source_key(s)
        seen.add(k)
        merged.append(s)
    extras = 0
    for s in cfg_sources:
        k = source_key(s)
        if k in seen:
            continue
        seen.add(k)
        merged.append(s)
        extras += 1
    return merged, len(db_sources), len(cfg_sources), extras

def fetch_rss(url, limit=10, _visited=None):
    """Fetch and parse RSS/Atom feed with endpoint fallback for stale URLs."""
    if not url:
        return ["• Error fetching RSS: missing url"]
    if _visited is None:
        _visited = set()
    key = canonical_url(url)
    if key in _visited:
        return [f"• Error fetching RSS {url}: fallback loop detected"]
    _visited.add(key)

    content = ""
    err = None
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ClawFeed Bot)"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        err = e
        try:
            content = e.read().decode("utf-8", errors="ignore")
        except Exception:
            content = ""
    except Exception as e:
        err = e

    items = _extract_feed_items(content, limit=limit) if content else []
    if not items and "arxiv.org/rss/" in str(url):
        items = _fetch_arxiv_api_from_rss_url(url, limit=limit)
    if items:
        return items

    for cand in _rss_fallback_candidates(url):
        if canonical_url(cand) in _visited:
            continue
        fallback_items = fetch_rss(cand, limit=limit, _visited=_visited)
        if fallback_items and not (len(fallback_items) == 1 and fallback_items[0].lower().startswith("• error fetching rss")):
            print(f"↪️ RSS fallback: {url} -> {cand}")
            return fallback_items

    if err:
        return [f"• Error fetching RSS {url}: {str(err)}"]
    return []

def fetch_hackernews(limit=15):
    """Fetch top stories from Hacker News"""
    try:
        req = urllib.request.Request(
            'https://hacker-news.firebaseio.com/v0/topstories.json',
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            ids = json.loads(resp.read())[:limit]
        
        stories = []
        for story_id in ids:
            try:
                req = urllib.request.Request(
                    f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json',
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    story = json.loads(resp.read())
                    if story and 'title' in story:
                        url = story.get('url', f"https://news.ycombinator.com/item?id={story_id}")
                        stories.append(f"• HN: {story['title']} ({url})")
            except Exception as e:
                continue
        return stories
    except Exception as e:
        return [f"• Error fetching HN: {str(e)}"]

def fetch_reddit(subreddit, limit=10):
    """Fetch hot posts from Reddit"""
    if not subreddit:
        return ["• Error fetching Reddit: missing subreddit"]
    sub = str(subreddit).strip().lstrip("/")
    if sub.lower().startswith("r/"):
        sub = sub[2:]
    if not sub:
        return ["• Error fetching Reddit: invalid subreddit"]
    try:
        req = urllib.request.Request(
            f'https://www.reddit.com/r/{sub}/hot.json?limit={limit}',
            headers={'User-Agent': 'Mozilla/5.0 (ClawFeed Bot)'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        
        posts = []
        for child in data['data']['children']:
            post = child['data']
            if not post.get('stickied'):
                posts.append(f"• r/{sub}: {post['title']} (https://reddit.com{post['permalink']})")
        return posts[:limit]
    except Exception as e:
        return [f"• Error fetching r/{sub}: {str(e)}"]

def fetch_github_trending(since='daily'):
    """Fetch trending GitHub repositories"""
    try:
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        req = urllib.request.Request(
            f'https://api.github.com/search/repositories?q=created:>{yesterday}&sort=stars&order=desc&per_page=10',
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/vnd.github.v3+json'}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        
        repos = []
        for item in data.get('items', [])[:8]:
            desc = item.get('description', 'No description') or 'No description'
            repos.append(f"• GitHub: {item['full_name']} - {desc[:60]} ({item['stargazers_count']} ⭐)")
        return repos
    except Exception as e:
        return [f"• Error fetching GitHub: {str(e)}"]


def fetch_website(url):
    """Fetch a website title as a lightweight fallback."""
    if not url:
        return ["• Error fetching website: missing url"]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (ClawFeed Bot)'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('utf-8', errors='ignore')
        m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        title = re.sub(r'\s+', ' ', (m.group(1).strip() if m else url))
        return [f"• Website: {title} ({url})"]
    except Exception as e:
        return [f"• Error fetching website {url}: {e}"]


def fetch_custom_api(url, limit=10):
    """Fetch headlines from a generic JSON API."""
    if not url:
        return ["• Error fetching custom_api: missing url"]
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (ClawFeed Bot)', 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        if isinstance(data, dict):
            items = data.get("items") or data.get("data") or data.get("results") or []
        elif isinstance(data, list):
            items = data
        else:
            items = []
        out = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("headline") or item.get("name")
            link = item.get("url") or item.get("link") or ""
            if title:
                out.append(f"• API: {title} ({link})")
        return out or [f"• API source returned no parseable headline items ({url})"]
    except Exception as e:
        return [f"• Error fetching API {url}: {e}"]


def annotate_source_items(source_name, items):
    """Attach source name to each item and remove generic prefixes."""
    annotated = []
    for item in items:
        if not isinstance(item, str):
            continue
        text = item.strip()
        if not text:
            continue
        if text.startswith("• "):
            text = text[2:].strip()
        if text.lower().startswith("error "):
            continue
        text = re.sub(r'^(RSS|HN|GitHub|Website|API)\s*:\s*', '', text, flags=re.IGNORECASE)
        annotated.append(f"• {source_name}: {text}")
    return annotated

def generate_with_gemini(content):
    """Generate digest using Gemini API"""
    global LAST_GEMINI_ERROR
    LAST_GEMINI_ERROR = ""
    if not GEMINI_API_KEY:
        LAST_GEMINI_ERROR = "No GOOGLE_API_KEY/GEMINI_API_KEY found in environment"
        print(f"⚠️ {LAST_GEMINI_ERROR}, fallback to raw aggregation.")
        return None
    
    highlights_target = max(12, min(32, len(content) // 8))
    prompt = f"""You are a tech news curator. Create a structured daily digest from the following sources.
Focus on AI research, prompt engineering, LLM management, hardware (ESP32), and modern dev stacks (Vercel/Supabase).
Ensure broad source coverage; do not over-focus on a single outlet.

FORMAT:
☀️ ClawFeed | {datetime.now().strftime('%A, %B %d, %Y')} Europe/Lisbon

🔥 Important (2-3 truly significant items)
• **[Headline]** — [2-3 sentence summary with key details, why it matters, and any actionable insights]

📰 Feed Highlights ({highlights_target} interesting items, diversified across many configured sources)
• **[Source Name]**: [Detailed summary of the article - what happened, why it is significant, and what it means for the reader]


SOURCES:
{chr(10).join(content)}
"""
    
    try:
        req = urllib.request.Request(
            'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({'contents': [{'parts': [{'text': prompt}]}]}).encode(),
            method='POST'
        )
        url = req.get_full_url() + f'?key={GEMINI_API_KEY}'
        req = urllib.request.Request(url, data=req.data, headers=req.headers, method='POST')
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            return result['candidates'][0]['content']['parts'][0]['text']
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode('utf-8', errors='ignore')
        except Exception:
            body = ""
        LAST_GEMINI_ERROR = f"HTTP {e.code}: {body[:300]}"
        print(f"⚠️ Gemini API error: {LAST_GEMINI_ERROR}")
        return None
    except Exception as e:
        LAST_GEMINI_ERROR = str(e)
        print(f"⚠️ Gemini API error: {LAST_GEMINI_ERROR}")
        return None

def create_digest(content, digest_type='daily', generated_by='fallback', gemini_error='', items_count=0, source_count=0, selected_sources=0, sources_with_content=0, skipped_sources=0, unsupported_sources=0, group_id=None, group_name=None):
    """Save digest to ClawFeed API"""
    metadata = {
        'generated_by': generated_by,
        'items_count': items_count,
        'sources_total': source_count,
        'sources_selected': selected_sources,
        'sources_with_content': sources_with_content,
        'sources_skipped': skipped_sources,
        'sources_unsupported': unsupported_sources,
        'generated_at': datetime.now().isoformat()
    }
    if gemini_error:
        metadata['gemini_error'] = gemini_error
    if group_name:
        metadata['group_name'] = group_name

    data = {
        'type': digest_type,
        'content': content,
        'metadata': json.dumps(metadata)
    }
    if group_id is not None:
        data['group_id'] = group_id
    
    req = urllib.request.Request(
        API_URL,
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        },
        data=json.dumps(data).encode(),
        method='POST'
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            return result.get('id')
    except Exception as e:
        print(f"❌ API error: {e}")
        return None

def generate_digest_for_group(group_id, group_info, sources_in_group, digest_type):
    """Generate a single digest for a specific group."""
    group_name = group_info.get('name', f'Group {group_id}')
    group_tz = group_info.get('timezone', 'UTC')

    print(f"\n{'='*60}")
    print(f"🏷️  Group: {group_name} (ID: {group_id}, TZ: {group_tz})")
    print(f"{'='*60}")

    all_content = []
    unsupported = 0
    sources_with_content = 0
    empty_or_failed = []

    for src in sources_in_group:
        name = src.get("name", "(unnamed)")
        stype = src.get("type", "")
        sconfig = parse_source_config(src.get("config"))
        limit = int(sconfig.get("limit", 10) or 10)

        print(f"📡 Fetching {name} ({stype})...")
        fetched = []

        if stype == "hackernews":
            fetched = fetch_hackernews(int(sconfig.get("limit", 15) or 15))
        elif stype == "reddit":
            fetched = fetch_reddit(sconfig.get("subreddit"), limit)
        elif stype in ("rss", "digest_feed"):
            fetched = fetch_rss(sconfig.get("url"), limit)
        elif stype == "github_trending":
            fetched = fetch_github_trending(sconfig.get("since", "daily"))
        elif stype == "website":
            wurl = sconfig.get("url")
            looks_like_feed = isinstance(wurl, str) and bool(re.search(r"(rss|atom|feed|\.xml)(\?|$)", wurl, re.IGNORECASE))
            if looks_like_feed:
                fetched = fetch_rss(wurl, limit)
                if not fetched or (len(fetched) == 1 and fetched[0].lower().startswith("• error fetching rss")):
                    fetched = fetch_website(wurl)
            else:
                fetched = fetch_website(wurl)
        elif stype == "custom_api":
            fetched = fetch_custom_api(sconfig.get("url"), limit)
        else:
            unsupported += 1
            continue

        normalized = annotate_source_items(name, fetched)
        if normalized:
            sources_with_content += 1
            all_content.extend(normalized)
        else:
            reason = fetched[0] if fetched else "No items returned"
            empty_or_failed.append(f"{name} ({stype}) -> {reason}")

    if unsupported:
        print(f"⚠️ Unsupported source types skipped: {unsupported}")
    if empty_or_failed:
        print(f"⚠️ Sources with no usable items: {len(empty_or_failed)}")
        for row in empty_or_failed:
            print(f"   - {row}")
    print(f"✅ Sources with usable content: {sources_with_content}/{len(sources_in_group)}")
    print(f"📊 Total items fetched: {len(all_content)}")

    if not all_content:
        print(f"⚠️ No content fetched for group '{group_name}'. Skipping digest generation.")
        return None

    # Try Gemini summarization
    print("🤖 Attempting Gemini summarization...")
    digest = generate_with_gemini(all_content)
    generated_by = 'gemini' if digest else 'fallback'

    if not digest:
        print("⚠️ Using fallback format with structured sections")
        important_items = all_content[:3]
        highlight_items = all_content[3:15]

        digest = f"""☀️ ClawFeed | {group_name} | {datetime.now().strftime('%A, %B %d, %Y')} {group_tz}

🔥 Important
{chr(10).join(important_items)}

📰 Feed Highlights
{chr(10).join(highlight_items)}

• None at this time

Note: Gemini summarization unavailable — showing aggregated feeds with basic formatting.
"""

    # Save to ClawFeed
    print(f"💾 Saving digest for group '{group_name}'...")
    digest_id = create_digest(
        digest,
        digest_type,
        generated_by=generated_by,
        gemini_error=LAST_GEMINI_ERROR,
        items_count=len(all_content),
        source_count=len(sources_in_group),
        selected_sources=len(sources_in_group),
        sources_with_content=sources_with_content,
        skipped_sources=0,
        unsupported_sources=unsupported,
        group_id=group_id,
        group_name=group_name
    )

    if digest_id:
        print(f"✅ Digest created! ID: {digest_id}")
        print(f"📖 View: http://127.0.0.1:8767/#digest-{digest_id}")
        return digest_id
    else:
        print(f"❌ Failed to create digest for group '{group_name}'")
        return None


def main():
    digest_type = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    if digest_type not in ALLOWED_DIGEST_TYPES:
        print(f"❌ Invalid digest type '{digest_type}'. Allowed: {', '.join(sorted(ALLOWED_DIGEST_TYPES))}")
        sys.exit(1)

    # Load sources and groups
    sources, db_count, cfg_count, cfg_extras = load_sources()
    groups = load_groups_from_db()

    if not sources:
        print("❌ No sources found (neither DB nor config.json).")
        sys.exit(1)

    print(f"📚 Loaded {len(sources)} sources (db={db_count}, config={cfg_count}, config_extras={cfg_extras})")
    print(f"🏷️  Loaded {len(groups)} active groups from database")
    print(f"🚀 Generating {digest_type} digests...")

    # Group sources by group_id
    grouped_sources = {}  # {group_id: [sources]}
    ungrouped_sources = []  # sources without a group

    skipped_disabled = 0
    skipped_schedule = 0

    for src in sources:
        if not src.get("enabled", True):
            skipped_disabled += 1
            continue

        digest_types = src.get("digestTypes") or ["daily"]
        if digest_type not in digest_types:
            skipped_schedule += 1
            continue

        gid = src.get("group_id")
        if gid and gid in groups:
            # Check if group supports this digest type
            group_digest_types = groups[gid].get('digest_types', [])
            if group_digest_types and digest_type not in group_digest_types:
                skipped_schedule += 1
                continue
            if gid not in grouped_sources:
                grouped_sources[gid] = []
            grouped_sources[gid].append(src)
        else:
            ungrouped_sources.append(src)

    # Print grouping statistics
    print(f"📚 Loaded {len(sources)} sources (db={db_count}, config={cfg_count}, config_extras={cfg_extras})")
    print(f"📊 Grouping summary:")
    print(f"   - {len(groups)} groups loaded")
    print(f"   - {len(grouped_sources)} groups with sources")
    print(f"   - {len(ungrouped_sources)} ungrouped sources")
    print(f"   - Skipped: disabled={skipped_disabled}, schedule_mismatch={skipped_schedule}")

    # Generate digest for each group
    results = []

    for group_id, group_sources in grouped_sources.items():
        group = groups.get(group_id)
        if not group:
            print(f"⚠️ Warning: Group {group_id} not found in groups dict, skipping...")
            continue

        group_name = group.get('name', f'Group {group_id}')
        print(f"\n{'='*60}")
        print(f"🔄 Processing group: {group_name}")
        print(f"{'='*60}")

        digest_id = generate_digest_for_group(
            group_id=group_id,
            group_info=group,
            sources_in_group=group_sources,
            digest_type=digest_type
        )

        if digest_id:
            results.append({'group': group_name, 'digest_id': digest_id, 'success': True})
        else:
            results.append({'group': group_name, 'digest_id': None, 'success': False})

    # Handle ungrouped sources as a "General" digest
    if ungrouped_sources:
        print(f"\n{'='*60}")
        print(f"🔄 Processing ungrouped sources")
        print(f"{'='*60}")

        # Create a synthetic group_info for ungrouped sources
        general_group_info = {
            'name': 'General',
            'description': 'Ungrouped sources',
            'digest_types': [digest_type]
        }

        digest_id = generate_digest_for_group(
            group_id=None,
            group_info=general_group_info,
            sources_in_group=ungrouped_sources,
            digest_type=digest_type
        )

        if digest_id:
            results.append({'group': 'General (ungrouped)', 'digest_id': digest_id, 'success': True})
        else:
            results.append({'group': 'General (ungrouped)', 'digest_id': None, 'success': False})

    # Print final summary
    print(f"\n{'='*60}")
    print(f"📋 Final Summary")
    print(f"{'='*60}")
    successful = sum(1 for r in results if r['success'])
    failed = len(results) - successful
    print(f"✅ Successfully generated: {successful} digests")
    if failed:
        print(f"❌ Failed: {failed} digests")

    for r in results:
        status = "✅" if r['success'] else "❌"
        if r['digest_id']:
            print(f"{status} {r['group']}: http://127.0.0.1:8767/#digest-{r['digest_id']}")
        else:
            print(f"{status} {r['group']}: Failed to create")

if __name__ == '__main__':
    main()
