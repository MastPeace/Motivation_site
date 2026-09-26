#!/usr/bin/env bash
# Render today's motivation poster and post it to a Telegram group topic.
# Uses Hermes' `hermes send` so no bot token is needed in the repo:
# hermes send --to telegram:<chat_id>:<thread_id> "MEDIA:<png>"
#
# Pipeline:
#   1. Sync today's daily.json from GitHub Pages (source of truth, updated
#      nightly by the repo's GitHub Action). Falls back to local data/daily.json.
#   2. Render a 1080x1350 poster PNG from it.
#   3. Post to the target group topic.
#
# Config via environment (set in ~/.hermes/.env):
#   MOTIVATION_TG_CHAT_ID    group chat_id (negative, starts with -100)
#   MOTIVATION_TG_THREAD     topic thread_id ("1" = General topic)
#   MOTIVATION_LANG          "en" or "ru" (default: en)
#   MOTIVATION_PAGES_BASE    optional override of "https://mastpeace.github.io/Motivation_site"
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
ROOT="${MOTIVATION_REPO:-/home/vovka/work/Motivation_site}"

# Load secrets/env (chat id, thread) from the same place Hermes reads them
if [ -f "$HERMES_HOME/.env" ]; then
  set -a; source "$HERMES_HOME/.env"; set +a
fi

CHAT_ID="${MOTIVATION_TG_CHAT_ID:-}"
THREAD="${MOTIVATION_TG_THREAD:-1}"
LANG="${MOTIVATION_LANG:-en}"
PAGES_BASE="${MOTIVATION_PAGES_BASE:-https://mastpeace.github.io/Motivation_site}"

if [ -z "$CHAT_ID" ]; then
  echo "ERROR: MOTIVATION_TG_CHAT_ID not set (put it in ~/.hermes/.env)" >&2
  exit 1
fi

# --- 1. sync today's pick from Pages (non-fatal) ---
if curl -fsS -m 30 "$PAGES_BASE/data/daily.json" -o "$ROOT/data/daily.json" 2>/dev/null; then
  echo "Synced daily.json from Pages: $(python3 -c "import json;print(json.load(open('$ROOT/data/daily.json')).get('date','?'))" 2>/dev/null || echo '?')"
else
  echo "WARN: could not reach Pages, using local data/daily.json" >&2
fi

# --- 2. render the poster ---
POSTER="$("$ROOT/venv/bin/python" "$ROOT/generator/render_poster.py" --lang "$LANG")"
echo "Rendered: $POSTER"

DATE_TAG="$(basename "$POSTER" .png | sed 's/^poster_//')"

# --- 3. post to the group topic (General = thread 1) ---
hermes send --to "telegram:${CHAT_ID}:${THREAD}" \
  --subject "Quote of the day · ${DATE_TAG}" \
  "MEDIA:${POSTER}"

echo "Posted to telegram:${CHAT_ID}:${THREAD}"