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

# Per-skill hermes metadata (tags + related)
HERMES_META = {
    "yc-office-hours":  {"tags": ["yc", "planning", "design-doc", "scope"],
                         "related_skills": ["yc-ceo-review"]},
    "yc-ceo-review":    {"tags": ["yc", "review", "scope", "planning"],
                         "related_skills": ["yc-eng-review", "yc-design-review"]},
    "yc-eng-review":    {"tags": ["yc", "review", "architecture", "planning"],
                         "related_skills": ["yc-design-review", "sec-cso"]},
    "yc-design-review": {"tags": ["yc", "review", "design", "ux"],
                         "related_skills": ["yc-devex-review"]},
    "yc-retro":         {"tags": ["yc", "retrospective", "learnings"],
                         "related_skills": ["yc-learn"]},
    "yc-devex-review":  {"tags": ["yc", "review", "devex", "onboarding"],
                         "related_skills": []},
    "sec-cso":          {"tags": ["security", "owasp", "stride", "threat-modeling"],
                         "related_skills": ["yc-eng-review"]},
    # yc-learn handled separately in Stage 2
}

HERMES_NOTE = (
    "> **Hermes adaptation note:** Ported from gstack (Claude Code plugin). "
    "Hermes has no native `AskUserQuestion` tool — when the skill says to use it, "
    "ask the user in a plain chat message and wait for the reply. "
    "Artifact paths use `~/.hermes/projects/<slug>/` instead of `~/.gstack/projects/<slug>/`. "
    "Skill content is preserved as-is from upstream — Plan Mode / Voice / Telemetry "
    "sections that reference Claude-Code-only bin tools degrade silently in hermes."
)

# Disclaimer мы сами добавили в Claude Code форке — для hermes лишний.
CLAUDE_DISCLAIMER_RE = re.compile(
    r"^> \*\*Adaptation note \(gstack personal fork\):\*\*.*?(?=\n\n|\Z)",
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
    return f"""---
name: {name}
description: {description}
version: 1.0.0
metadata:
  hermes:
    tags: [{tags}]
{related_block}
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
