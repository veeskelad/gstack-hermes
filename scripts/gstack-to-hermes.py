#!/usr/bin/env python3
"""
Minimal adapter from gstack (Claude Code) SKILL.md to Hermes Agent format.

Принцип: меняем ТОЛЬКО то, без чего hermes не примет скилл или что
конкретно Claude-Code-specific. Контент скиллов не трогаем — Plan Mode,
Voice, Telemetry, Continuous Checkpoint и прочий boilerplate остаётся.

Что делает:
1. Frontmatter — добавляет hermes-recommended поля (version, metadata.hermes.tags, related_skills)
2. Удаляет наш Claude-Code-specific disclaimer-блок (`> **Adaptation note (gstack personal fork):**`)
3. Добавляет hermes adaptation note (одна строка про AskUserQuestion)
4. Sed: ~/.gstack/projects/<slug>/ → ~/.hermes/projects/<slug>/
5. Sed: $(git rev-parse --show-toplevel 2>/dev/null || pwd) → ${HERMES_PROJECT:-$(pwd)}
6. Sed: /yc-review → /requesting-code-review
7. Side-files (sections/, specialists/, ACKNOWLEDGEMENTS.md) — только пункты 4–6

yc-learn пропускаем — он отдельно перезаписывается в Stage 2.
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS = REPO_ROOT / "skills"

# Per-skill hermes metadata.
# - tags          → for hub UI / discovery
# - related_skills → soft pointers (no flow semantics)
# - successor     → next pipeline step (used by HERMES_NOTE auto-progression)
HERMES_META = {
    "yc-office-hours":   {"tags": ["yc", "planning", "design-doc", "scope"],
                          "related_skills": ["yc-ceo-review"],
                          "successor": "yc-ceo-review"},
    "yc-ceo-review":     {"tags": ["yc", "review", "scope", "planning"],
                          "related_skills": ["yc-eng-review", "yc-design-review"],
                          "successor": "writing-plans"},
    "yc-eng-review":     {"tags": ["yc", "review", "architecture", "planning"],
                          "related_skills": ["yc-design-review", "sec-cso"],
                          "successor": "sec-cso"},
    "yc-design-review":  {"tags": ["yc", "review", "design", "ux"],
                          "related_skills": ["yc-devex-review"],
                          "successor": "writing-plans"},
    "yc-retro":          {"tags": ["yc", "retrospective", "learnings"],
                          "related_skills": ["yc-learn"],
                          "successor": "yc-learn"},
    "yc-devex-review":   {"tags": ["yc", "review", "devex", "onboarding"],
                          "related_skills": [],
                          "successor": "writing-plans"},
    "sec-cso":           {"tags": ["security", "owasp", "stride", "threat-modeling"],
                          "related_skills": ["yc-eng-review"],
                          "successor": "executing-plans"},
    "autoplan":          {"tags": ["yc", "review", "batch", "orchestrator"],
                          "related_skills": ["yc-ceo-review", "yc-eng-review", "yc-design-review", "yc-devex-review"],
                          "successor": "executing-plans"},
    "ship":              {"tags": ["workflow", "release", "deploy", "version-bump"],
                          "related_skills": ["yc-retro"],
                          "successor": "yc-retro"},
    "document-generate": {"tags": ["documentation", "scaffolding"],
                          "related_skills": [],
                          "successor": None},  # terminal / orthogonal
    # yc-learn handled separately (Stage 2); successor=None
    # gstack (entry-point menu) handled separately; successor=None
}

HERMES_NOTE = (
    "> **Hermes adaptation note:** Ported from gstack (Claude Code plugin). "
    "Hermes has no native `AskUserQuestion` tool — use the native `clarify` tool "
    "(`clarify_tool(question, choices)`) instead when the skill body says to ask the "
    "user for a choice. For open-ended free-text follow-up, just ask in a plain chat "
    "message and wait for the reply. "
    "Artifact paths use `~/.hermes/projects/<slug>/` instead of `~/.gstack/projects/<slug>/`. "
    "Skill content is preserved as-is from upstream — Plan Mode / Voice / Telemetry "
    "sections that reference Claude-Code-only bin tools degrade silently in hermes.\n"
    ">\n"
    "> **Language:** The skill body is written in English, but respond to the user in "
    "the user's language. If the user writes in Russian — translate all questions, "
    "option labels, and prose to Russian on the fly. Keep technical identifiers — "
    "file paths, code, slash-commands, env vars, YAML keys — in their original form.\n"
    ">\n"
    "> **Output formatting (Telegram/Discord/Slack gateways):**\n"
    "> - In **prose reply text** (regular message body, including numbered/bulleted "
    "lists you write directly to the user) — `**markdown bold**` is OK for option labels "
    "and key terms. The gateway's `format_message` converts it to platform-native bold. "
    "Example: `1. **A) SCOPE EXPANSION** — расширяем scope в 4 направлениях`.\n"
    "> - In `clarify_tool` calls — the `choices` array values must be **PLAIN TEXT** "
    "with NO `**bold**` or `__underline__`. The inline-keyboard render path does NOT "
    "apply MarkdownV2 conversion, so double-asterisks leak as literal characters.\n"
    "> - Additional emphasis: «кавычки-ёлочки» for quotes, ALL CAPS for category labels, "
    "`→` prefix for list items. Single `*italic*` and inline `\\`code\\`` are fine "
    "in both prose and clarify choices.\n"
    ">\n"
    "> **Pipeline auto-progression:** If this skill's frontmatter has "
    "`metadata.hermes.pipeline_successor: <next-skill-name>`, then AFTER you finish "
    "the skill body (delivered the design doc / review / artifact and saved any files), "
    "you MUST call `clarify_tool` with question `\"Готово. Дальше — /<next-skill-name>?\"` "
    "and choices `[\"Да, запусти /<next>\", \"Пропустить\", \"Сделать другое\"]` "
    "(translated to the user's language). On user's pick:\n"
    "> - «Да»: `read_file('~/.hermes/skills/gstack-hermes/<next>/SKILL.md')`, then follow its "
    "instructions step-by-step (hermes has no `skill_load` tool — read+execute is the path).\n"
    "> - «Пропустить»: end the conversation cleanly.\n"
    "> - «Сделать другое»: ask what they want and route from there.\n"
    "> If `pipeline_successor` is not set or is null — skip this step (terminal skill).\n"
    "> Also append a one-line text reminder before the clarify call: "
    "`**Next pipeline step:** /<next-skill-name>` — so the user sees it even if the "
    "clarify card is dismissed."
)

# Disclaimer мы сами добавили в Claude Code форке — для hermes лишний.
CLAUDE_DISCLAIMER_RE = re.compile(
    r"^> \*\*Adaptation note \(gstack personal fork\):\*\*.*?(?=\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Existing hermes note from a prior translation run — strip to keep translator idempotent.
EXISTING_HERMES_NOTE_RE = re.compile(
    r"^> \*\*Hermes adaptation note:\*\*.*?(?=\n\n|\Z)",
    re.MULTILINE | re.DOTALL,
)

# Path / command replacements (применяются и к SKILL.md, и к side-files)
SED_RULES = [
    (re.compile(r"~/\.gstack/projects/"),                "~/.hermes/projects/"),
    (re.compile(r"~/\.gstack/learnings\.jsonl"),         "~/.hermes/projects/<slug>/learnings.jsonl"),
    (re.compile(r"\$\(git rev-parse --show-toplevel 2>/dev/null \|\| pwd\)"),
                                                         '${HERMES_PROJECT:-$(pwd)}'),
    (re.compile(r"/yc-review\b"),                        "/requesting-code-review"),
]


def apply_sed_rules(text: str) -> str:
    for pattern, repl in SED_RULES:
        text = pattern.sub(repl, text)
    return text


def parse_frontmatter(text: str):
    """Return (frontmatter_text, body_text). Raises if missing."""
    lines = text.splitlines(keepends=False)
    if not lines or lines[0].strip() != "---":
        raise ValueError("no frontmatter")
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[1:i]), "\n".join(lines[i + 1:])
    raise ValueError("unclosed frontmatter")


def extract_field(frontmatter: str, key: str):
    """Quick extract for top-level scalar key (name/description)."""
    m = re.search(rf"^{key}:\s*(.+)$", frontmatter, re.MULTILINE)
    return m.group(1).strip() if m else None


def build_hermes_frontmatter(name: str, description: str, meta: dict) -> str:
    tags = ", ".join(meta["tags"])
    related = ", ".join(meta["related_skills"])
    related_block = f"    related_skills: [{related}]" if related else "    related_skills: []"
    successor = meta.get("successor")
    successor_block = f"\n    pipeline_successor: {successor}" if successor else ""
    return f"""---
name: {name}
description: {description}
version: 1.0.0
metadata:
  hermes:
    tags: [{tags}]
{related_block}{successor_block}
---"""


def adapt_skill_md(path: Path, skill_name: str):
    raw = path.read_text(encoding="utf-8")
    fm, body = parse_frontmatter(raw)

    name = extract_field(fm, "name") or skill_name
    description = extract_field(fm, "description") or f"{skill_name} (adapted from gstack)"

    if skill_name not in HERMES_META:
        # yc-learn or unknown — skip, handled separately
        return False

    new_fm = build_hermes_frontmatter(name, description, HERMES_META[skill_name])

    # Strip Claude Code disclaimer
    body = CLAUDE_DISCLAIMER_RE.sub("", body, count=1).lstrip("\n")

    # Strip prior hermes note(s) — could be multiple from earlier non-idempotent runs
    body = EXISTING_HERMES_NOTE_RE.sub("", body).lstrip("\n")

    # Apply sed rules
    body = apply_sed_rules(body)

    # Prepend hermes adaptation note
    final = new_fm + "\n\n" + HERMES_NOTE + "\n\n" + body
    if not final.endswith("\n"):
        final += "\n"

    path.write_text(final, encoding="utf-8")
    return True


def adapt_side_file(path: Path):
    """Side-files get only sed rules — no frontmatter changes, no notes."""
    raw = path.read_text(encoding="utf-8")
    new = apply_sed_rules(raw)
    if new != raw:
        path.write_text(new, encoding="utf-8")
        return True
    return False


def main():
    print(f"{'skill':<22} {'SKILL.md':>9} {'side-files':>11}")
    print("-" * 45)
    for skill_dir in sorted(SKILLS.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        skill_changed = adapt_skill_md(skill_md, skill)
        side_count = 0
        for sf in skill_dir.rglob("*"):
            if not sf.is_file():
                continue
            if sf == skill_md:
                continue
            if sf.suffix == ".md":
                if adapt_side_file(sf):
                    side_count += 1
            elif sf.suffix == ".json":
                if adapt_side_file(sf):
                    side_count += 1
        mark = "✓" if skill_changed else "skip"
        print(f"{skill:<22} {mark:>9} {side_count:>11}")


if __name__ == "__main__":
    main()
