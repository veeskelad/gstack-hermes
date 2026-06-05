---
name: yc-learn
description: "Capture, search, and prune project learnings. Writes ### sections to ~/.hermes/memories/lessons.md (compatible with the file-size-guard hook for auto-archive). Use when the user wants to record an insight, ask 'what have we learned about X', or 'didn't we fix this before?'."
version: 1.0.0
metadata:
  hermes:
    tags: [yc, learnings, memory, retrospective]
    related_skills: [yc-retro]
---

> **Hermes adaptation note:** Ported from gstack (Claude Code plugin). This is the only skill rewritten — original gstack version wrote JSONL into `~/.gstack/projects/<slug>/learnings.jsonl`. Hermes-native version writes Markdown `###` sections to `~/.hermes/memories/lessons.md`, which integrates with the built-in `file-size-guard` hook (auto-archives half the sections to `~/.hermes/cold/archive/lessons-archive.md` when file exceeds 5000 bytes).

## When to invoke this skill

Use when the user:
- Wants to record a lesson learned: "запомни этот урок", "save this insight", "learning", `/yc-learn <topic>`
- Asks about past patterns: "what have we learned about X", "didn't we fix this before?", "show learnings on Y"
- Wants to prune outdated lessons: "почисти lessons", "stale learnings"

Proactively suggest invoking this skill after debugging a hard bug, after a retro (`/yc-retro`), or after a non-obvious fix lands.

## Three modes

### Mode 1 — Capture a new learning

Trigger: explicit `/yc-learn <topic>`, "save this lesson", "запомни этот урок", or proactive suggestion after a hard problem is resolved.

Steps:

1. **Detect project slug** (used only for tagging the section, not as a separate file):
   ```bash
   SLUG="${HERMES_PROJECT:-$(basename "$(pwd)")}"
   ```
   If running in gateway-mode without cwd context, ask the user: «Какой проект? (slug)»

2. **Ask the user (in chat) for the three required fields:**
   - **Триггер / Trigger** — what happened, the observation
   - **Урок / Lesson** — what was understood
   - **Применять / Apply when** — when this lesson kicks in next time

   If the user only gives one line, infer the other two from conversation context and confirm before writing.

3. **Append a `###`-level section to `~/.hermes/memories/lessons.md`:**

   Format:
   ```markdown
   ### YYYY-MM-DD HH:MM — [SLUG] short-title

   **Триггер:** <trigger>
   **Урок:** <lesson>
   **Применять:** <apply-when>
   ```

   Example:
   ```markdown
   ### 2026-06-05 14:30 — [gstack-hermes] tap manifest is optional

   **Триггер:** Думал нужен skills.toml в корне для hermes tap.
   **Урок:** Hermes принимает tap без манифеста — структура `skills/<name>/SKILL.md` достаточна. `skills.sh.json` опционален, только для категоризации.
   **Применять:** Когда оформляешь новый tap для hermes — не выдумывай obligatory manifests, проверь сначала.
   ```

   Bash one-liner to append:
   ```bash
   LESSONS=~/.hermes/memories/lessons.md
   TS=$(date +'%Y-%m-%d %H:%M')
   cat >> "$LESSONS" <<EOF

   ### $TS — [$SLUG] <short-title>

   **Триггер:** <trigger>
   **Урок:** <lesson>
   **Применять:** <apply-when>
   EOF
   ```

4. **Confirm to the user** with a single line: «Урок зафиксирован в `~/.hermes/memories/lessons.md`. `file-size-guard` сам архивирует, когда файл перерастёт лимит.»

### Mode 2 — Search / review existing learnings

Trigger: "what have we learned about X", "show learnings on Y", "didn't we fix this before?", `/yc-learn search <query>`.

Steps:

1. Search both the live file and the archive:
   ```bash
   LESSONS=~/.hermes/memories/lessons.md
   ARCHIVE=~/.hermes/cold/archive/lessons-archive.md

   for FILE in "$LESSONS" "$ARCHIVE"; do
     [ -f "$FILE" ] || continue
     echo "=== $FILE ==="
     awk -v q="$QUERY" '
       /^### / { if (in_match) print sec; in_match=0; sec=$0"\n"; next }
       { sec = sec $0 "\n" }
       tolower(sec) ~ tolower(q) { in_match=1 }
       END { if (in_match) print sec }
     ' "$FILE"
   done
   ```

2. If nothing found, say so explicitly: «Ничего не нашёл по запросу `<query>` ни в lessons.md, ни в архиве.»

3. If found, summarize hits in chat: section heading + 1-line distillation of the lesson.

### Mode 3 — Prune stale learnings

Trigger: "почисти lessons", "prune stale", `/yc-learn prune`.

Steps:

1. Read `~/.hermes/memories/lessons.md`, split by `### `.
2. For each section, ask the user (in chat, present 5 at a time): «Этот урок ещё актуален?» — list options [keep / archive / delete].
3. Apply decisions:
   - **keep** — no change
   - **archive** — move section to `~/.hermes/cold/archive/lessons-archive.md` (append), remove from live
   - **delete** — drop section entirely
4. Report tally: «Сохранено: N, в архив: M, удалено: K.»

## Conventions

- **Heading level**: `###` only (level-3). Hermes `file-size-guard` splits by `### ` headings — this format is required for auto-archive to work.
- **Timestamp**: `YYYY-MM-DD HH:MM` (local time), placed right after `### `.
- **Slug in brackets**: `[<slug>]` so search by project is `grep '\[gstack-hermes\]' lessons.md`.
- **Body**: three required bold labels — `**Триггер:**`, `**Урок:**`, `**Применять:**`. Free-form text after each; can span multiple lines.
- **Language**: prefer the user's language for the body (mostly Russian in this setup). Headings and labels — same bilingual format above.

## Integration with hermes file-size-guard

The native `~/.hermes/hooks/file-size-guard/handler.py` watches `lessons.md` (limit 5000 bytes). When exceeded:
- Splits content by `### ` headings.
- Moves the older half to `~/.hermes/cold/archive/lessons-archive.md`.
- Keeps the newer half in the live file.

This means yc-learn never needs to do its own archiving. Just append `###` sections and the hook does the rest.

## Integration with yc-retro

After running `/yc-retro`, the retro will often surface 2–4 lessons worth capturing. The retro skill should suggest «Закрепить этот урок? `/yc-learn`» for each — accepting the suggestion invokes this skill.

## Edge cases

- **No `~/.hermes/memories/lessons.md` yet**: create the file with a header `# Lessons learned\n\n` then append.
- **Slug undetectable** (gateway mode, no project context): use `[general]` as fallback slug; user can edit later.
- **Search returns archive hit**: explicitly mention "(from archive)" in the summary so the user knows it's older.
