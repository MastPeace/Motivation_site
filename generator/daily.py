#!/usr/bin/env python3
"""
Daily motivation generator.

Runs in GitHub Actions (cron) with NO LLM. Pipeline:
  1. Fetch world news (Google News RSS, keyless).
  2. Score headlines against a fixed theme whitelist (keyword matching).
  3. Pick today's theme (dominant); fall back to a rotating base theme if news is weak.
  4. Select a quote tagged with that theme, excluding all quotes used in the last COOLDOWN_DAYS.
  5. Fetch a correlated image (Unsplash if UNSPLASH_ACCESS_KEY set, else seeded Picsum).
  6. Write data/daily.json + append to data/history.json (deterministic per date).

Usage:
  UNSPLASH_ACCESS_KEY=xxx python3 generator/daily.py      # full run
  python3 generator/daily.py --date 2026-09-15            # run for a specific date
"""
import argparse, datetime, hashlib, json, os, random, sys, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
THEMES_PATH = os.path.join(DATA, "themes.json")
QUOTES_PATH = os.path.join(DATA, "quotes.json")
DAILY_PATH = os.path.join(DATA, "daily.json")
HISTORY_PATH = os.path.join(DATA, "history.json")

NEWS_FEEDS = [
    "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss?hl=ru&gl=RU&ceid=RU:ru",
]
COOLDOWN_DAYS = 30
USER_AGENT = "Mozilla/5.0 (compatible; motivation-daily/1.0)"


def log(*a):
    print("[daily]", *a, flush=True)


def load_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def ds_of_date(date):
    return int(date.replace("-", ""))


def date_seed(date):
    """Deterministic pseudo-random for a date, so all visitors see the same pick all day."""
    return random.Random(ds_of_date(date))


def fetch_feeds():
    texts = []
    for url in NEWS_FEEDS[:1]:  # primary feed only; RU feed used for language fallback
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as r:
                root = ET.fromstring(r.read())
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
            for it in items[:40]:
                t = it.findtext("title")
                if t:
                    texts.append(t)
        except Exception as e:
            log(f"feed {url} failed: {e}")
    return texts


def pick_theme(headlines, themes, fallback_pool, rng):
    """Score headlines against themes; return (theme_name, score, matched_sample)."""
    if not headlines:
        return fallback_pool[rng.randrange(len(fallback_pool))], 0, None
    blob = " ".join(headlines).lower()
    best_name, best_score, best_hit = None, 0, None
    for t in themes:
        score = 0
        hits = []
        for kw in t["keywords"]:
            c = blob.count(kw.lower())
            score += c
            if c and len(hits) < 3:
                hits.append(kw)
        if score > best_score:
            best_name, best_score, best_hit = t["name"], score, hits
    if best_name is None or best_score < 1:
        # news too weak/irrelevant -> deterministic rotating base theme for the date
        return fallback_pool[rng.randrange(len(fallback_pool))], 0, None
    return best_name, best_score, best_hit


def select_quote(quotes, history, theme, rng):
    candidates = [q for q in quotes if theme in q.get("tags", [])]
    used_ids = {h.get("id") for h in history[-COOLDOWN_DAYS:]}
    fresh = [q for q in candidates if q["id"] not in used_ids]
    if not fresh:
        fresh = [q for q in quotes if q["id"] not in used_ids]  # ignore theme, still respect cooldown
    pool = fresh or candidates or quotes
    return rng.choice(pool)


def image_url(theme, rng, unsplash_key=None, date=None):
    q = theme.get("unsplash_query", theme["name"])
    if unsplash_key:
        import urllib.parse
        url = "https://api.unsplash.com/search/photos?query={}&per_page=15&orientation=landscape&client_id={}".format(
            urllib.parse.quote_plus(q), unsplash_key)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.load(r)
            photos = data.get("results", [])
            if photos:
                pick = rng.choice(photos)
                u = pick["urls"]
                download = pick.get("links", {}).get("download_location")
                return u.get("raw", u.get("regular")), download
        except Exception as e:
            log(f"unsplash failed: {e}")
    # fallback: seeded random Picsum photo (stable per date)
    seed = ds_of_date((date or datetime.date.today().isoformat()))
    return f"https://picsum.photos/seed/{seed}/1200/800", None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--cooldown", type=int, default=COOLDOWN_DAYS)
    args = ap.parse_args()

    date = args.date or datetime.date.today().isoformat()
    themes_data = load_json(THEMES_PATH, {})
    themes = themes_data.get("themes", []) if isinstance(themes_data, dict) else themes_data
    fallback_pool = themes_data.get("fallback_pool", ["hope"]) if isinstance(themes_data, dict) else ["hope"]
    quotes = load_json(QUOTES_PATH, [])
    history = load_json(HISTORY_PATH, [])

    rng = date_seed(date)
    headlines = fetch_feeds()
    theme, score, sample = pick_theme(headlines, themes, fallback_pool, rng)
    theme_obj = next((t for t in themes if t["name"] == theme), themes[0] if themes else {})

    if history and history[-1].get("date") == date:
        log(f"already generated for {date}, skip")
        return

    quote = select_quote(quotes, history, theme, rng)
    img, download_loc = image_url(theme_obj, rng, os.environ.get("UNSPLASH_ACCESS_KEY"), date)

    entry = {
        "date": date,
        "id": quote["id"],
        "theme": theme,
        "en": quote["en"],
        "ru": quote["ru"],
        "author": quote["author"],
        "image": img,
        "source": quote.get("source", ""),
        "news_score": score,
        "news_sample": sample,
    }
    if download_loc:
        entry["unsplash_ack"] = download_loc  # used in a post-run to acknowledge Unsplash (toS)

    save_json(DAILY_PATH, entry)
    history.append({"date": date, "id": quote["id"], "theme": theme})
    save_json(HISTORY_PATH, history[-365:])  # keep a rolling year

    log(f"date={date} theme={theme} score={score} quote_id={quote['id']} ({quote['en'][:40]}...) cooldown_window={args.cooldown}d")


if __name__ == "__main__":
    main()