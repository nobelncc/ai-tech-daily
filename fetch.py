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
    Calls the
