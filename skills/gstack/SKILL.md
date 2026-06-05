---
name: gstack
description: "MENU. Use ONLY when the user asks to see the gstack pipeline menu, list its commands, asks 'what's in gstack', 'show pipeline', 'не помню команд', or types /gstack. Shows a two-level inline-keyboard via hermes clarify_tool — L1 categories → L2 concrete skill → reads + executes the chosen /yc-* skill."
version: 1.0.0
metadata:
  hermes:
    tags: [gstack, menu, entry-point, orchestrator, pipeline]
    related_skills: [yc-office-hours, yc-ceo-review, yc-eng-review, autoplan, ship, sec-cso]
---

> **Hermes adaptation note:** This is the entry-point menu for the gstack-hermes pipeline (8 review/workflow/security skills). It uses the native `clarify_tool` for two-level navigation. Respond in the user's language (translate option labels on the fly). For clarify `choices` arrays — plain text, no `**bold**`. For prose around them — `**bold**` is fine.

## When to invoke

Use this skill when the user:
- Types `/gstack`
- Asks «покажи меню gstack», «что есть в gstack», «список команд», «не помню что есть»
- Wants to discover the pipeline rather than recall a specific `/yc-*` command

**Do NOT** invoke when the user already named a specific skill (`/yc-office-hours`, `/sec-cso`, etc.) — that's a direct call, not a menu request.

## Step 1 — Check for prior pipeline state

Before showing L1, read the last 50 lines of `~/.hermes/memories/MEMORY.md` and look for a `### Next Steps (gstack pipeline, ...)` section. If found within the last 24 hours and the suggested next step is one of our 11 skills — add a 5th "continue" option to L1.

```bash
tail -50 ~/.hermes/memories/MEMORY.md | grep -A2 "### Next Steps (gstack pipeline"
```

## Step 2 — L1 clarify (4 or 5 categories)

Call `clarify_tool` with question `"Что хочешь сделать?"` (or translated) and these choices (PLAIN TEXT — no markdown):

```
choices = [
  "🧠 Review — обсудить идею или ревью плана",
  "⚙️ Workflow — батч-ревью, выкатить, документация",
  "📝 Retro & Learn — ретро и записать урок",
  "🔒 Security — OWASP + STRIDE угрозы"
]
```

If Step 1 found a fresh pending next-step, **prepend** a 5th option:
`"↪ Продолжить с прошлого шага: /<skill-name>"`

## Step 3 — L2 clarify (per selected category)

After the L1 selection, branch:

### If "🧠 Review"
```
clarify(
  question="Какой review?",
  choices=[
    "/yc-office-hours — новая идея, 6 forcing вопросов",
    "/yc-ceo-review — scope-ревью в 4 режимах",
    "/yc-eng-review — арх-ревью плана: edge cases, тесты",
    "/yc-design-review — UX-ревью / AI-slop detection"
  ]
)
```

### If "⚙️ Workflow"
```
clarify(
  question="Какой workflow?",
  choices=[
    "/autoplan — батч CEO + Eng + Design + DevEx ревью разом",
    "/ship — tests → review → version bump → deploy",
    "/document-generate — сгенерить доки для модуля",
    "/yc-devex-review — time-to-hello-world DX аудит"
  ]
)
```

### If "📝 Retro & Learn"
```
clarify(
  question="Retro или learn?",
  choices=[
    "/yc-retro — еженедельное ретро",
    "/yc-learn — записать урок в ~/.hermes/memories/lessons.md"
  ]
)
```

### If "🔒 Security"
Only one skill — skip L2 clarify, ask directly:
> «Запускаю /sec-cso для OWASP + STRIDE threat-modeling. Что ревьюим — план, PR, конкретный модуль?»

### If "↪ Продолжить" (5th option, if present)
Skip L2 — pull the suggested skill name from MEMORY.md and proceed to Step 4.

## Step 4 — Load and execute the chosen skill

Hermes has **no `skill_load` tool** for agent-side invocation. To run the chosen skill:

1. Extract the slash-command from the L2 selection (e.g. `/yc-office-hours` → name `yc-office-hours`).
2. Read the skill file:
   ```python
   read_file("~/.hermes/skills/gstack-hermes/<name>/SKILL.md")
   ```
3. **Follow the SKILL.md body step-by-step as if it were your current task.** The skill's HERMES_NOTE applies (language, formatting, auto-progression).
4. Announce to the user before starting: `Запускаю /<name> — <one-line описание>`.

**Fallback if `read_file` is unavailable:**
Ask the user to send the command themselves: `«Нажми или напиши /<name> чтобы запустить.»` Then end the turn.

## Edge cases

- **L1 «Other (type answer)»** — user wants something not in our menu. Ask: «Что именно? Если не помнишь команды — попробуй описать задачу, я найду подходящий скилл по описанию.»
- **L2 «Other (type answer)»** — same as L1 within the category context.
- **User dismisses clarify** (closes Telegram, no answer in 5 min) — clarify_tool times out, just end the conversation cleanly. The user can re-type `/gstack` later.
- **Skill body too large to read in one shot** — read with `length` param (e.g. first 200 lines) and continue iteratively. All our skills are ≤90KB, fits in one read.

## Pipeline reference

The pipeline mapping (which skill suggests which next) lives in:
- Hook side: `~/.hermes/hooks/pipeline-next-step/pipeline-config.json`
- Skill side: each skill's `metadata.hermes.pipeline_successor` frontmatter field

These should agree. If they diverge — the frontmatter wins (it's what the model sees), but report the drift to the user so they can update.

## Why `/gstack` exists

11 skills + the broader hermes pipeline (`writing-plans`, `executing-plans`, `requesting-code-review`) is too many to recall from memory. `/gstack` is the **discovery surface** — for routine flows users learn the specific `/yc-*` commands and skip the menu.
