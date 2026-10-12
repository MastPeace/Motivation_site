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
import argparse, datetime, json, os, random, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
THEMES_PATH = os.path.join(DATA, "themes.json")
QUOTES_PATH = os.path.join(DATA, "quotes.json")
DAILY_PATH = os.path.join(DATA, "daily.json")
HISTORY_PATH = os.path.join(DATA, "history.json")

# Keywords in themes.json are English, so only the English feed is scored.
NEWS_FEEDS = ["https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"]
COOLDOWN_DAYS = 30
THEME_REPEAT_DAYS = 3      # themes used in the last N days get a score penalty (variety)
THEME_REPEAT_FACTOR = 0.5
MIN_WORD_STEM = 4          # keywords shorter than this must match a whole word ("ai" != "said")
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
    tmp = path + ".tmp"  # atomic replace: never leave a half-written JSON file
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def ds_of_date(date):
    return int(date.replace("-", ""))


def date_seed(date):
    """Deterministic pseudo-random for a date, so all visitors see the same pick all day."""
    return random.Random(ds_of_date(date))


def fetch_feeds():
    texts = []
    for url in NEWS_FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=25) as r:
                root = ET.fromstring(r.read())
            channel = root.find("channel")
            items = channel.findall("item") if channel is not None else []
            for it in items[:40]:
                t = it.findtext("title")
                if t:
                    # Google News appends " - Publisher"; drop it so outlet names don't score.
                    texts.append(re.sub(r"\s+-\s+[^-]+$", "", t))
        except Exception as e:
            log(f"feed {url} failed: {e}")
    return texts


def keyword_regex(kw):
    """Word-boundary matcher. Long keywords are stems ("persever" -> perseverance);
    short ones must be a whole word, so "ai" no longer matches "said"/"again"/"Spain"."""
    k = re.escape(kw.lower())
    if len(kw) < MIN_WORD_STEM:
        return re.compile(r"\b" + k + r"\b")
    return re.compile(r"\b" + k)


def pick_theme(headlines, themes, fallback_pool, rng, recent_themes=()):
    """Score themes by how many headlines mention them (each headline counts once per
    theme). Recently used themes are down-weighted. Returns (theme, score, sample_keywords)."""
    def fallback():
        return fallback_pool[rng.randrange(len(fallback_pool))], 0, None

    if not headlines:
        return fallback()
    lowered = [h.lower() for h in headlines]
    scored = []
    for t in themes:
        hits, count = [], 0
        for kw in dict.fromkeys(t["keywords"]):  # dedupe, keep order
            rx = keyword_regex(kw)
            n = sum(1 for h in lowered if rx.search(h))
            if n:
                count += n
                if len(hits) < 3:
                    hits.append(kw)
        if count:
            w = THEME_REPEAT_FACTOR if t["name"] in recent_themes else 1.0
            scored.append((count * w, count, t["name"], hits))
    if not scored:
        return fallback()
    top = max(s[0] for s in scored)
    best = [s for s in scored if s[0] == top]
    _, count, name, hits = best[rng.randrange(len(best))]  # deterministic tie-break
    return name, count, hits


def select_quote(quotes, history, theme, rng):
    candidates = [q for q in quotes if theme in q.get("tags", [])]
    used_ids = {h.get("id") for h in history}
    fresh = [q for q in candidates if q["id"] not in used_ids]
    if not fresh:
        fresh = [q for q in quotes if q["id"] not in used_ids]  # ignore theme, still respect cooldown
    pool = fresh or candidates or quotes
    return rng.choice(pool)


UTM = "utm_source=daily_motivation&utm_medium=referral"


def image_url(theme, rng, unsplash_key=None, date=None):
    """Return (url, photo_meta). photo_meta is None for the Picsum fallback, else
    {"name","link","download"} for Unsplash attribution + download tracking."""
    q = theme.get("unsplash_query", theme["name"])
    if unsplash_key:
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
                raw = u.get("raw")
                src = raw + ("&" if "?" in raw else "?") + "w=1200&h=800&fit=crop&q=80" if raw else u.get("regular")
                user = pick.get("user", {})
                meta = {
                    "name": user.get("name", ""),
                    "link": (user.get("links", {}).get("html", "https://unsplash.com") + "?" + UTM),
                    "download": pick.get("links", {}).get("download_location"),
                }
                return src, meta
        except Exception as e:
            log(f"unsplash failed: {type(e).__name__}")  # never log the URL: it contains the key
    # fallback: seeded random Picsum photo (stable per date)
    seed = ds_of_date((date or datetime.date.today().isoformat()))
    return f"https://picsum.photos/seed/{seed}/1200/800", None


def track_download(meta, unsplash_key):
    """Unsplash API guideline: ping download_location when a photo is used."""
    if not (meta and meta.get("download") and unsplash_key):
        return
    try:
        sep = "&" if "?" in meta["download"] else "?"
        req = urllib.request.Request(f"{meta['download']}{sep}client_id={unsplash_key}", headers={"User-Agent": USER_AGENT})
        urllib.request.urlopen(req, timeout=15).read()
    except Exception as e:
        log(f"unsplash download ping failed: {type(e).__name__}")


def moscow_today():
    """Today's date in Moscow (UTC+3), used for the deterministic daily pick."""
    return (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=3)).date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None)
    ap.add_argument("--cooldown", type=int, default=COOLDOWN_DAYS)
    args = ap.parse_args()

    date = args.date or moscow_today()
    themes_data = load_json(THEMES_PATH, {})
    themes = themes_data.get("themes", []) if isinstance(themes_data, dict) else themes_data
    fallback_pool = themes_data.get("fallback_pool", ["hope"]) if isinstance(themes_data, dict) else ["hope"]
    quotes = load_json(QUOTES_PATH, [])
    history = load_json(HISTORY_PATH, [])

    if any(h.get("date") == date for h in history):
        log(f"already generated for {date}, skip")
        return

    rng = date_seed(date)
    headlines = fetch_feeds()
    recent = {h.get("theme") for h in history[-THEME_REPEAT_DAYS:]}
    theme, score, sample = pick_theme(headlines, themes, fallback_pool, rng, recent)
    theme_obj = next((t for t in themes if t["name"] == theme), themes[0] if themes else {})

    quote = select_quote(quotes, history[-args.cooldown:], theme, rng)
    key = os.environ.get("UNSPLASH_ACCESS_KEY")
    img, photo = image_url(theme_obj, rng, key, date)

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
    if photo:
        entry["photo"] = {"name": photo["name"], "link": photo["link"]}
        track_download(photo, key)

    save_json(DAILY_PATH, entry)
    h_entry = {"date": date, "id": quote["id"], "theme": theme, "image": img}
    if photo:
        h_entry["photo"] = entry["photo"]
    history.append(h_entry)
    save_json(HISTORY_PATH, history[-365:])  # keep a rolling year

    log(f"date={date} theme={theme} score={score} quote_id={quote['id']} ({quote['en'][:40]}...) cooldown_window={args.cooldown}d")


if __name__ == "__main__":
    main()