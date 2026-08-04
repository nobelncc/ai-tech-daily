"""
Automated News Aggregator - Fetch & Summarize Script
=======================================================
This script runs automatically (via GitHub Actions, see .github/workflows/update.yml).
It does NOT need to be run manually once set up.

What it does, step by step:
1. Reads the list of RSS sources from sources.json
2. Fetches the latest items from each source
3. Skips any item it has already processed before (deduplication)
4. Sends new items to Google Gemini (AI, free tier) to write a short, original 2-3 line summary
5. Saves everything into data/articles.json, which the website reads from

If you are not a developer: you do not need to understand this file.
You only ever need to edit sources.json to add/remove news sources.
"""

import json
import os
import sys
import time
import hashlib
import re
from datetime import datetime, timezone

import feedparser
import requests

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
DATA_FILE = "data/articles.json"
SOURCES_FILE = "sources.json"
MAX_STORED_ARTICLES = 300          # keeps the JSON file (and site) from growing forever
MAX_NEW_SUMMARIES_PER_RUN = 15       # safety cap so one run stays comfortably inside the free tier's per-minute limit
SECONDS_BETWEEN_AI_CALLS = 4         # small pause so requests don't burst past the free tier's requests-per-minute limit
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL_FALLBACKS = [
    "gemini-2.5-flash",          # stable, fast, reliable - tried first
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",    # preview model - powerful but sometimes overloaded/slow, kept as last resort
]  # tried in this order, first one that works wins

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def log(msg):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {msg}", flush=True)


def load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log(f"WARNING: could not read {path}: {e}")
    return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def make_id(url, title):
    """Creates a stable unique ID for an article so we can detect duplicates."""
    raw = (url or "") + "|" + (title or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def clean_html(raw_html):
    """Strips HTML tags from RSS descriptions."""
    if not raw_html:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarize_with_ai(title, source_text, source_name):
    """
    Calls the Google Gemini API (free tier) to produce a short, original summary.
    Returns a plain string. Falls back to a trimmed original snippet if the
    API call fails for any reason (so the pipeline never crashes because of this) -
    e.g. if the free daily quota is temporarily used up.

    Tries a short list of model names in order, in case one is unavailable
    for this particular API key/account (this varies more than it should).
    """
    fallback = (source_text[:220] + "...") if len(source_text) > 220 else source_text

    if not GEMINI_API_KEY:
        log("WARNING: GEMINI_API_KEY not set - using fallback snippet instead of AI summary")
        return fallback

    prompt = (
        "You are writing a short, original news summary for a news aggregator website. "
        "Do NOT copy sentences verbatim from the source. Rewrite the key point in your own words. "
        "Keep it to 2-3 sentences, neutral tone, no opinions.\n\n"
        f"Source: {source_name}\n"
        f"Headline: {title}\n"
        f"Original snippet: {source_text[:800]}\n\n"
        "Write only the summary, nothing else."
    )

    last_error_detail = ""
    for model_name in GEMINI_MODEL_FALLBACKS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        try:
            response = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}]},
                timeout=15,
            )
            if response.status_code != 200:
                # Capture Google's actual explanation, not just the status code -
                # this is what tells us WHY it failed (bad model name, quota, permissions, etc.)
                last_error_detail = f"{response.status_code} - {response.text[:300]}"
                log(f"WARNING: Gemini model '{model_name}' failed for '{title}': {last_error_detail}")
                continue  # try the next model name in the fallback list

            result = response.json()
            candidates = result.get("candidates", [])
            if not candidates:
                last_error_detail = f"200 OK but no candidates returned: {response.text[:300]}"
                continue
            parts = candidates[0].get("content", {}).get("parts", [])
            summary = " ".join(p.get("text", "") for p in parts).strip()
            if summary:
                return summary
        except Exception as e:
            last_error_detail = str(e)
            log(f"WARNING: Gemini model '{model_name}' raised an exception for '{title}': {e}")
            continue

    log(f"WARNING: AI summary failed for '{title}' on all models tried ({last_error_detail}) - using fallback snippet")
    return fallback


def fetch_source(source):
    """Fetches and parses one RSS feed. Never raises - returns [] on failure."""
    name = source.get("name", "Unknown Source")
    url = source.get("rss_url")
    category = source.get("category", "General")
    items = []
    try:
        # Many sites (Reddit, some news sites with bot protection) block requests
        # that don't look like a real browser/RSS reader. Sending a normal User-Agent
        # fixes most of these silently-failing feeds.
        feed = feedparser.parse(
            url,
            request_headers={
                "User-Agent": "Mozilla/5.0 (compatible; NewsAggregatorBot/1.0; +https://github.com/)"
            },
        )
        if feed.bozo and not feed.entries:
            status = getattr(feed, "status", "unknown")
            log(f"WARNING: could not parse feed for '{name}' ({url}) - HTTP status: {status}")
            return items
        for entry in feed.entries[:15]:  # only look at the 15 newest items per source per run
            title = entry.get("title", "").strip()
            link = entry.get("link", "").strip()
            if not title or not link:
                continue
            summary_raw = entry.get("summary", "") or entry.get("description", "")
            published = entry.get("published", "") or entry.get("updated", "")
            items.append({
                "source": name,
                "category": category,
                "title": title,
                "url": link,
                "raw_snippet": clean_html(summary_raw),
                "published_raw": published,
            })
    except Exception as e:
        log(f"ERROR fetching '{name}': {e}")
    return items


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    log("Starting news aggregator run...")

    sources_config = load_json(SOURCES_FILE, {"sources": []})
    sources = sources_config.get("sources", [])
    if not sources:
        log("ERROR: no sources found in sources.json - nothing to do.")
        sys.exit(0)

    existing_data = load_json(DATA_FILE, {"articles": [], "last_updated": None})
    existing_articles = existing_data.get("articles", [])
    seen_ids = {a["id"] for a in existing_articles}

    log(f"Loaded {len(existing_articles)} previously stored articles.")
    log(f"Checking {len(sources)} sources...")

    all_new_items = []
    for source in sources:
        fetched = fetch_source(source)
        log(f"  {source.get('name')}: found {len(fetched)} items")
        all_new_items.extend(fetched)

    # Group by category and interleave (round-robin) so that if there are more
    # new items than we can AI-summarize in one run, every category still gets
    # a fair share instead of the first-listed category (e.g. AI & Tech) using
    # up the entire budget before other categories are ever reached.
    by_category = {}
    for item in all_new_items:
        by_category.setdefault(item["category"], []).append(item)

    interleaved_items = []
    while any(by_category.values()):
        for cat in list(by_category.keys()):
            if by_category[cat]:
                interleaved_items.append(by_category[cat].pop(0))

    new_articles = []
    summarized_count = 0

    for item in interleaved_items:
        article_id = make_id(item["url"], item["title"])
        if article_id in seen_ids:
            continue  # already processed before - skip (this IS the deduplication step)
        seen_ids.add(article_id)

        if summarized_count < MAX_NEW_SUMMARIES_PER_RUN:
            summary = summarize_with_ai(item["title"], item["raw_snippet"], item["source"])
            summarized_count += 1
            if summarized_count < MAX_NEW_SUMMARIES_PER_RUN:
                time.sleep(SECONDS_BETWEEN_AI_CALLS)
        else:
            # AI summary budget used up for this run - still publish the article
            # (using the original snippet) instead of dropping it. It will simply
            # look like a direct excerpt rather than an AI-rewritten summary.
            # This guarantees every category still appears on the site every run.
            summary = (item["raw_snippet"][:220] + "...") if len(item["raw_snippet"]) > 220 else item["raw_snippet"]

        new_articles.append({
            "id": article_id,
            "source": item["source"],
            "category": item["category"],
            "title": item["title"],
            "url": item["url"],
            "summary": summary,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        })

    log(f"New articles this run: {len(new_articles)}")

    combined = new_articles + existing_articles
    combined = combined[:MAX_STORED_ARTICLES]

    output = {
        "site_name": sources_config.get("site_name", "News Aggregator"),
        "site_description": sources_config.get("site_description", ""),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "articles": combined,
    }
    save_json(DATA_FILE, output)
    log(f"Saved {len(combined)} total articles to {DATA_FILE}. Done.")


if __name__ == "__main__":
    main()
