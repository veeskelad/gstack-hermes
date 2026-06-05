"""
pipeline-next-step — hermes hook (event: agent:end).

After the agent finishes processing a user message that invoked a gstack
pipeline skill (e.g. `/yc-office-hours`), append a `### Next Steps`
section to ~/.hermes/memories/MEMORY.md so the next session sees a
suggestion for the next logical step (loaded via memory prefetch).

Throttle: do not repeat the same suggestion more than once per hour.
"""
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta

HERMES = os.path.expanduser("~/.hermes")
MEMORY_FILE = os.path.join(HERMES, "memories", "MEMORY.md")
STATE_FILE = os.path.join(HERMES, "state", "pipeline-suggest.json")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "pipeline-config.json")

THROTTLE_SECONDS = 3600  # 1 hour
TZ = timezone(timedelta(hours=8))  # match other hermes hooks

# Match leading slash-command in the user message, e.g.
# "/yc-office-hours my idea about X" → "yc-office-hours"
COMMAND_RE = re.compile(r"^\s*/([a-z][a-z0-9-]*(?::[a-z][a-z0-9-]*)?)", re.IGNORECASE)


def _load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"last_suggestions": {}}


def _save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _extract_command(message):
    if not isinstance(message, str):
        return None
    m = COMMAND_RE.match(message)
    return m.group(1).lower() if m else None


def _get_user_message(context):
    if isinstance(context, dict):
        return context.get("message") or context.get("user_message")
    return getattr(context, "user_message", None) or getattr(context, "message", None)


def _append_suggestion(prev_skill, next_step, why):
    os.makedirs(os.path.dirname(MEMORY_FILE), exist_ok=True)
    ts = datetime.now(TZ).strftime("%Y-%m-%d %H:%M")
    section = (
        f"\n### Next Steps (gstack pipeline, {ts})\n\n"
        f"Just ran `/{prev_skill}`. Logical next step: `/{next_step}` "
        f"— {why}.\n"
        f"_Suggested by gstack-hermes pipeline-next-step hook. "
        f"Ignore if not relevant._\n"
    )
    # Append (memory prefetch will pick it up in the next session)
    with open(MEMORY_FILE, "a", encoding="utf-8") as f:
        f.write(section)


async def handle(event_type, context):
    if event_type != "agent:end":
        return

    user_msg = _get_user_message(context)
    prev_skill = _extract_command(user_msg)
    if not prev_skill:
        return

    config = _load_config()
    entry = config.get(prev_skill)
    if not entry:
        return  # not a known pipeline step, silently skip

    next_step = entry.get("next")
    why = entry.get("why", "")
    if not next_step:
        return

    state = _load_state()
    last = state.get("last_suggestions", {})
    now = int(time.time())
    suggestion_key = f"{prev_skill}->{next_step}"
    last_ts = last.get(suggestion_key, 0)
    if now - last_ts < THROTTLE_SECONDS:
        return  # throttled

    _append_suggestion(prev_skill, next_step, why)
    last[suggestion_key] = now
    state["last_suggestions"] = last
    _save_state(state)
