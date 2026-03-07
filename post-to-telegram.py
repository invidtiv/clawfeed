#!/usr/bin/env python3
"""
Post ClawFeed digests to Telegram group with topics.
Sends full content split into multiple messages.
Usage: python3 post-to-telegram.py <digest_type>
"""
import os
import sys
import json
import urllib.request
import time
from pathlib import Path

API_URL = os.environ.get("API_URL", "http://127.0.0.1:8767/api/digests")
TELEGRAM_GROUP = int(os.environ.get("TELEGRAM_CHAT_ID", "0") or "0")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Group mappings (group_id -> (topic_name, thread_id))
GROUPS = {
    3: ("🇵🇹 Portugal News", 173),
    4: ("🌈 The No News Channel", 175),
    5: ("🎶 Music", 174),
    6: ("🔧 Framework", 176),
    None: ("📰 General", 177),
}

def get_latest_digest(digest_type, group_id=None):
    """Get latest digest from API."""
    url = f"{API_URL}?type={digest_type}&limit=5"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            for d in data:
                if group_id is None:
                    if d.get('group_id') is None:
                        return d
                elif d.get('group_id') == group_id:
                    return d
            return None
    except Exception as e:
        print(f"❌ Error fetching digest: {e}")
        return None

def send_message(text, thread_id):
    """Send a message to Telegram topic."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    data = {
        "chat_id": TELEGRAM_GROUP,
        "message_thread_id": thread_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode(),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result.get('ok', False)
    except Exception as e:
        print(f"❌ Error sending: {e}")
        return False

def split_content(content, max_len=3800):
    """Split content into chunks under max_len characters."""
    chunks = []
    
    # Try to split at section boundaries first
    sections = content.split('\n\n')
    current_chunk = ""
    
    for section in sections:
        if len(current_chunk) + len(section) + 2 > max_len:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = section
        else:
            if current_chunk:
                current_chunk += "\n\n"
            current_chunk += section
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # If any chunk is still too long, split by lines
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_len:
            final_chunks.append(chunk)
        else:
            lines = chunk.split('\n')
            current = ""
            for line in lines:
                if len(current) + len(line) + 1 > max_len:
                    if current:
                        final_chunks.append(current.strip())
                    current = line
                else:
                    if current:
                        current += "\n"
                    current += line
            if current:
                final_chunks.append(current.strip())
    
    return final_chunks

def post_digest_to_topic(digest, topic_name, thread_id):
    """Post full digest content split into messages."""
    content = digest.get('content', '')
    digest_id = digest.get('id')
    
    if not content:
        print("⚠️ Empty content")
        return False
    
    # Escape HTML special chars
    content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Add header
    header = f"<b>📰 {topic_name}</b>\n{'='*30}\n\n"
    full_content = header + content
    
    # Split into chunks
    chunks = split_content(full_content)
    
    print(f"  → Split into {len(chunks)} messages")
    
    for i, chunk in enumerate(chunks, 1):
        # Add part indicator if multiple chunks
        if len(chunks) > 1:
            chunk += f"\n\n<i>(Part {i}/{len(chunks)})</i>"
        
        if send_message(chunk, thread_id):
            print(f"  ✅ Part {i}/{len(chunks)}")
        else:
            print(f"  ❌ Part {i}/{len(chunks)} failed")
            return False
        
        # Small delay to avoid rate limits
        if i < len(chunks):
            time.sleep(1)
    
    # Send footer with link
    footer = f"\n🔗 <a href='http://vmi2916953.tail652dda.ts.net:8767/#digest-{digest_id}'>View on ClawFeed</a>"
    send_message(footer, thread_id)
    
    return True

def main():
    print("WARNING: DEPRECATED: This script is superseded by the Telegram posting in generate-digest.py. Consider removing it.")
    digest_type = sys.argv[1] if len(sys.argv) > 1 else 'daily'
    
    print(f"🚀 Posting {digest_type} digests to Telegram...")
    
    for group_id, (topic_name, thread_id) in GROUPS.items():
        print(f"\n📤 {topic_name}...")
        
        digest = get_latest_digest(digest_type, group_id)
        if not digest:
            print("  ⚠️ No digest found")
            continue
        
        if post_digest_to_topic(digest, topic_name, thread_id):
            print(f"  ✅ Complete")
        else:
            print(f"  ❌ Failed")
        
        # Delay between topics to avoid rate limits
        time.sleep(2)
    
    print("\n✅ All done!")

if __name__ == '__main__':
    main()