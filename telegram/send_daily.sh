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

# --- 3. post to the group topic (General = thread 1), silent ---
# Direct Bot API: sendPhoto with disable_notification=true (no notification sound).
# Uses TELEGRAM_BOT_TOKEN from ~/.hermes/.env — never stored in the repo.
CAPTION="Quote of the day · ${DATE_TAG}"
RESP="$("$ROOT/venv/bin/python" - "${TELEGRAM_BOT_TOKEN:-}" "${CHAT_ID}" "${THREAD}" "${POSTER}" "${CAPTION}" <<'PY'
import sys, json, os, urllib.request, urllib.parse, mimetypes

token, chat_id, thread, poster, caption = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]

boundary = "----MotivationBoundary----"
with open(poster, "rb") as f:
    filedata = f.read()
mt = mimetypes.guess_type(poster)[0] or "image/png"
name = os.path.basename(poster)

def part(name_, value, is_file=False):
    if is_file:
        return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name_}"; '
                f'filename="{value}"\r\nContent-Type: {mt}\r\n\r\n').encode() + filedata + b"\r\n"
    return (f'--{boundary}\r\nContent-Disposition: form-data; name="{name_}"\r\n\r\n'
            f'{value}\r\n').encode()

def body_parts():
    yield part("chat_id", chat_id)
    # Topic routing: General topic = OMIT message_thread_id entirely (explicit "1" is
    # rejected by the API; numeric ids above 1 refer to created forum sections).
    if thread not in ("", "1", "general"):
        yield part("message_thread_id", thread)
    yield part("photo", name, True)
    yield part("caption", caption)
    yield part("disable_notification", "true")
    yield f"--{boundary}--\r\n".encode()

body = b"".join(body_parts())
url = f"https://api.telegram.org/bot{token}/sendPhoto"
req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "motivation-poster/1.0"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.load(r)
        if d.get("ok"):
            print("sent ok, message_id=" + str(d["result"]["message_id"]))
        else:
            print("Telegram error: " + str(d.get("description")), file=sys.stderr)
            sys.exit(1)
except urllib.error.HTTPError as e:
    print("HTTP " + str(e.code) + ": " + e.read().decode()[:300], file=sys.stderr)
    sys.exit(1)
PY
)"
echo "$RESP"
echo "Posted (silent) to telegram:${CHAT_ID}:${THREAD}"