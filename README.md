# gstack-hermes

YC-style review pipeline + threat-modeling for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Adapted from [garrytan/gstack](https://github.com/garrytan/gstack) (Claude Code plugin) with minimal changes — full skill content preserved upstream, only the bits that genuinely break in Hermes are touched.

## What you get

11 skills:

| Skill | What it does |
|---|---|
| `yc-office-hours` | YC-style 6 forcing questions for a new idea. Saves a design doc to `~/.hermes/projects/<slug>/designs/`. |
| `yc-ceo-review` | CEO-mode plan review: 4 scope modes (Expansion / Selective / Hold / Reduction). |
| `yc-eng-review` | Engineering-mode plan review: diagrams, edge cases, test plan. |
| `yc-design-review` | UX/UI plan review, AI-slop detection. |
| `yc-devex-review` | Time-to-hello-world DX audit. |
| `autoplan` | Batch orchestrator — runs CEO + Eng + Design + DevEx reviews sequentially with auto-decisions. |
| `yc-retro` | Weekly engineering retrospective. |
| `yc-learn` | Capture / search / prune project learnings. Writes `###` sections to `~/.hermes/memories/lessons.md` (compatible with `file-size-guard` hook). |
| `sec-cso` | Chief Security Officer mode: OWASP Top 10 + STRIDE threat-modeling on a plan. |
| `document-generate` | Generate missing documentation for a feature, module, or entire project. |
| `ship` | Release workflow: detect base branch, run tests, review diff, bump VERSION, update CHANGELOG, push. |

Plus one hook:

| Hook | What it does |
|---|---|
| `pipeline-next-step` | After `agent:end`, appends a `### Next Steps` suggestion to `MEMORY.md` if you just ran a `/yc-*` or `/sec-cso` skill. Throttled to once per hour per suggestion. |

## Install

### 1. Add the tap

```bash
hermes skills tap add veeskelad/gstack-hermes
```

### 2. Install skills

Pick the ones you want:

```bash
hermes skills install veeskelad/gstack-hermes/yc-office-hours
hermes skills install veeskelad/gstack-hermes/yc-ceo-review
hermes skills install veeskelad/gstack-hermes/yc-eng-review
hermes skills install veeskelad/gstack-hermes/yc-design-review
hermes skills install veeskelad/gstack-hermes/yc-devex-review
hermes skills install veeskelad/gstack-hermes/autoplan
hermes skills install veeskelad/gstack-hermes/yc-retro
hermes skills install veeskelad/gstack-hermes/yc-learn
hermes skills install veeskelad/gstack-hermes/sec-cso
hermes skills install veeskelad/gstack-hermes/document-generate
hermes skills install veeskelad/gstack-hermes/ship
```

> **Note:** hermes security scanner may flag the skills as `dangerous` (false positive on bash patterns like `AGENTS.md`, `rm`, `sudo`). If installs are blocked, sideload manually:
>
> ```bash
> git clone https://github.com/veeskelad/gstack-hermes /tmp/gstack-hermes
> mkdir -p ~/.hermes/skills/gstack-hermes
> cp -r /tmp/gstack-hermes/skills/* ~/.hermes/skills/gstack-hermes/
> ```

### 3. Install the pipeline-next-step hook (optional)

```bash
git clone https://github.com/veeskelad/gstack-hermes /tmp/gstack-hermes
cp -r /tmp/gstack-hermes/hooks/pipeline-next-step ~/.hermes/hooks/
```

Make sure `hooks_auto_accept: true` is set in `~/.hermes/config.yaml`, or accept the hook on first use.

## Pipeline

```
new idea ────────────► /yc-office-hours
                           │ (design doc)
                           ▼
scope unclear ───────► /yc-ceo-review
                           │ (4-mode scope review)
                           ▼
need task plan ──────► /writing-plans            (hermes-native)
                           │
              ┌────────────┴─────────────┐
              ▼                          ▼
  individual reviews            batch shortcut:
   /yc-eng-review                    /autoplan
   /yc-design-review                 (CEO+Eng+Design+DevEx in one shot)
   /yc-devex-review
   /sec-cso (if auth/payments)
              │                          │
              └────────────┬─────────────┘
                           ▼
                  /executing-plans            (hermes-native)
                           │
                           ▼
                  /requesting-code-review     (hermes-native)
                           │
                           ▼
                       /ship                  (tests + version bump + deploy)
                           │
                           ▼ (post-release)
                       /yc-retro
                           │
                           ▼
                       /yc-learn

orthogonal (any time):  /document-generate (scaffold docs for module/project)
```

After each pipeline skill, `pipeline-next-step` hook writes a suggestion to `MEMORY.md` — it'll be picked up by hermes memory prefetch on the next session. Pure recommendation; ignore if not relevant.

## Why not just use upstream gstack?

[`garrytan/gstack`](https://github.com/garrytan/gstack) is already in hermes `DEFAULT_TAPS`, so you can pull it directly. This fork differs in:

- **Smaller scope** — 8 skills (vs 35+). Only the review/retro/learn/CSO subset that complements hermes uniquely. We dropped `yc-review` because hermes has `software-development/requesting-code-review` v2.0.0 which is more mature (baseline-aware, auto-fix loop).
- **No `gstack-*` binary dependencies** — original skills call `~/.claude/skills/gstack/bin/gstack-config` and similar that don't exist in hermes; we removed those touchpoints.
- **Hermes adaptation note** at the top of each skill — explicit guidance for the model about `AskUserQuestion` → plain chat replacement, path differences.
- **`yc-learn`** rewritten to write `###` sections to `~/.hermes/memories/lessons.md` (auto-archived by hermes's `file-size-guard`) instead of separate `learnings.jsonl`.
- **Pipeline hook** rewritten as native Python async handler on `agent:end` (was Claude-Code `Stop` hook).

## Skill format

Each skill is a single `SKILL.md` with YAML frontmatter:

```yaml
---
name: yc-office-hours
description: "..."
version: 1.0.0
metadata:
  hermes:
    tags: [yc, planning, design-doc, scope]
    related_skills: [yc-ceo-review]
---
```

Some skills have side-files (`sections/`, `specialists/`, `ACKNOWLEDGEMENTS.md`) — referenced from the body via `${HERMES_SKILL_DIR}`.

Most skills contain Plan Mode / Voice / Telemetry / Continuous Checkpoint sections from upstream gstack that reference Claude-Code-only `gstack-config` binaries. These degrade silently in hermes — the model sees them but the bin calls fail gracefully (and most are wrapped in `2>/dev/null || true`). We kept them as-is to stay close to upstream; if context size becomes an issue, run `scripts/strip-boilerplate.py` (not included here, but the original is in [garrytan/gstack](https://github.com/garrytan/gstack)).

## Updating

```bash
hermes skills check    # see which installed skills have upstream changes
hermes skills update   # pull and reinstall
```

## Credits

- Upstream: [garrytan/gstack](https://github.com/garrytan/gstack) (MIT)
- Hermes: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- This fork: minimal adapter for hermes — see `scripts/gstack-to-hermes.py` for the exact transformations.

## License

MIT — see [LICENSE](LICENSE).
