# Plan: gstack-hermes tap repo + hermes update

## Context

У меня есть локальный плагин `~/.claude/plugins/gstack/` для Claude Code с 9 YC-style review-скиллами и pipeline auto-suggest хуками. На сервере `frankfurt` (aisy-de, 43.131.58.150) живёт Hermes Agent v0.15.1 — собственная AI-agent платформа от NousResearch с почти идентичным форматом скиллов (Markdown + YAML frontmatter), системой hooks и нативным механизмом tap-репозиториев для загрузки скиллов из GitHub.

Исследование показало: **7 из 9 скиллов** уникально дополняют hermes (review-пайплайн в YC-стиле + CSO threat-modeling), остальные 2 уже есть нативно или конфликтуют. Hermes на сервере отстаёт на 659 коммитов от origin — обновление тоже нужно. Цель: оформить адаптированные скиллы как публичный GitHub-репо `veeskelad/gstack-hermes`, подключить через `hermes skills tap add`, добавить native python-handler для pipeline auto-suggest, обновить сам hermes.

## Решения, зафиксированные на Phase 3

- **GitHub owner:** `veeskelad`, репо `gstack-hermes`, публичный
- **Pipeline hook:** native python handler в `~/.hermes/hooks/pipeline-next-step/` на событии `agent:end`, пишет suggestion в `~/.hermes/memories/MEMORY.md` под секцию `### Next Steps`
- **yc-learn:** рефактор под нативный `~/.hermes/memories/lessons.md` (интегрируется с file-size-guard)
- **Hermes update:** сначала проверить `hermes upgrade` команду, fallback на `git pull + pip install -e .`
- **Скиллы для портирования (7):** yc-office-hours, yc-ceo-review, yc-eng-review, yc-design-review, yc-retro, yc-devex-review, sec-cso + рефакторнутый yc-learn
- **НЕ портируем:** yc-review (в hermes уже лучше — `software-development/requesting-code-review` v2.0.0)

## Stage 0 — Локальный staging

Создать рабочую копию для трансформации (не трогая исходный плагин):
- `~/work/gstack-hermes/` — staging directory
- Скопировать 8 скиллов (без `yc-review`) из `~/.claude/plugins/gstack/skills/` сохраняя side-files (`sections/`, `specialists/`, `ACKNOWLEDGEMENTS.md`)

## Stage 1 — Минимальная адаптация скиллов

**Принцип:** скиллы должны остаться **максимально близкими к оригиналу**. Меняем ТОЛЬКО то, без чего hermes не запустит или что специфично для Claude Code и бессмысленно в hermes. НЕ trogaem контентную часть, Plan Mode секции, Voice/Writing Style, Telemetry, Continuous Checkpoint, Operational Self-Improvement boilerplate — оставляем как есть (деградируют тихо, но это часть оригинального дизайна gstack).

**Скрипт-переводчик** `~/work/gstack-hermes/scripts/gstack-to-hermes.py` делает только:

1. **Frontmatter** — добавить рекомендуемые hermes-поля поверх существующих `name` + `description`:
   ```yaml
   ---
   name: yc-office-hours              # уже есть
   description: "..."                  # уже есть
   version: 1.0.0                      # ДОБАВИТЬ
   metadata:                           # ДОБАВИТЬ
     hermes:
       tags: [yc, review, planning]
       related_skills: [yc-ceo-review]
   ---
   ```

2. **Удалить disclaimer-блок** который мы сами добавили через `add-disclaimer.py` (Claude Code-specific предупреждение про `gstack-*` бинари). Это не часть оригинального gstack-контента — мы его сами вставили для нашего Claude Code форка. В hermes он лишний.

3. **AskUserQuestion** — нативного tool в hermes нет. Минимальная замена: в каждом месте, где SKILL.md инструктирует «Use AskUserQuestion with options X/Y/Z», превратить в «Ask the user (in chat/CLI): X / Y / Z». Текст вопроса и опции — без изменений. Только механизм доставки.

4. **Артефактные пути** — sed по простым правилам:
   - `~/.gstack/projects/<slug>/` → `~/.hermes/projects/<slug>/`
   - `~/.gstack/learnings.jsonl` → `~/.hermes/projects/<slug>/learnings.jsonl` (для yc-learn перезапишется в Stage 2)
   - Прямые ссылки на `~/.claude/plugins/gstack/` (если есть) → ссылка на репо

5. **Git workflow fallback** (только там где встречается) — `$(git rev-parse --show-toplevel 2>/dev/null || pwd)` → `${HERMES_PROJECT:-$(pwd)}`. В gateway-режиме (Telegram) git недоступен.

6. **Slash-команды** — `/yc-review` → `/requesting-code-review` (нативный аналог в hermes). Остальные `/yc-*` остаются как есть (hermes их поймёт).

7. **Side-files** (`sections/`, `specialists/`, `ACKNOWLEDGEMENTS.md`) — копируем 1:1, применяя ТОЛЬКО те же sed-правила про пути и `/yc-review`. Контент не трогаем.

**Что НЕ делаем (важно):**
- НЕ запускаем `strip-boilerplate.py` (Plan Mode/Voice/Telemetry секции остаются)
- НЕ переписываем тело скиллов, не упрощаем, не «улучшаем»
- НЕ срезаем строки даже если они кажутся device-specific — минимальные правки, ничего больше

**Источник:** `~/.claude/plugins/gstack/skills/<name>/SKILL.md` + side-files
**Цель:** `~/work/gstack-hermes/skills/<name>/SKILL.md` + side-files

## Stage 2 — yc-learn рефактор

Полностью переписать `yc-learn/SKILL.md` под нативную hermes memory-модель:
- Вместо `~/.gstack/projects/<slug>/learnings.jsonl` — пишет markdown-секции в `~/.hermes/memories/lessons.md`
- Формат секции совместим с `file-size-guard` hook (split по `###` headings):
  ```markdown
  ### [project-slug] <YYYY-MM-DD> — <короткое-название>
  
  **Триггер:** что случилось
  **Урок:** что усвоено
  **Применять:** когда повторится
  ```
- При переполнении lessons.md существующий `file-size-guard` сам архивирует половину секций в `~/.hermes/cold/archive/lessons-archive.md` — никакой дополнительной инфры не нужно

## Stage 3 — Pipeline auto-suggest handler

Создать в репо как deliverable: `~/work/gstack-hermes/hooks/pipeline-next-step/{HOOK.yaml, handler.py}` + `pipeline-config.json`. Пользователь потом скопирует в `~/.hermes/hooks/pipeline-next-step/` на сервере (в README укажу команды).

**HOOK.yaml:**
```yaml
name: pipeline-next-step
description: "After agent completes a /yc-* skill, suggest next pipeline step in MEMORY.md"
events: [agent:end]
```

**handler.py** (async, по образцу `~/.hermes/hooks/file-size-guard/handler.py`):
- Читает `context['response']` (first 500 chars assistant response) и `context['message']` (user message)
- По regex'у определяет какой `/yc-*` скилл только что отработал (`/yc-office-hours`, `/yc-ceo-review`, и т.д.)
- Загружает `pipeline-config.json` (рядом с handler.py), достаёт next_step + reason
- Применяет throttle: не повторяет ту же подсказку чаще раза в час (через `~/.hermes/state.db` или sidecar JSON)
- Аппендит секцию `### Next Steps` в `~/.hermes/memories/MEMORY.md`:
  ```
  ### Next Steps (gstack pipeline, <timestamp>)
  После `/yc-office-hours` логично запустить `/yc-ceo-review` — <reason>.
  ```
- При следующей сессии hermes memory_manager.prefetch_all() подтянет MEMORY.md в context — пользователь увидит подсказку

**pipeline-config.json** — копия `~/.claude/plugins/gstack/state/pipeline-config.json` с поправками на hermes-имена скиллов (`yc-review` → `requesting-code-review`).

## Stage 4 — Tap-repo обвязка

В корень `~/work/gstack-hermes/`:

**README.md** — sanitized, без personal references. Содержит:
- Что это, какие 8 скиллов, в чём ценность
- `hermes skills tap add veeskelad/gstack-hermes`
- `hermes skills install veeskelad/gstack-hermes/yc-office-hours` (и т.д.)
- Инструкция как установить pipeline-next-step hook (cp в `~/.hermes/hooks/`)
- Описание pipeline flow с диаграммой
- Credits — `garrytan/gstack` (original) + adapt notes

**skills.sh.json** — категоризация:
```json
{
  "groupings": [
    {"title": "YC Plan Review", "skills": ["yc-office-hours", "yc-ceo-review", "yc-eng-review", "yc-design-review", "yc-devex-review"]},
    {"title": "Retrospective & Learning", "skills": ["yc-retro", "yc-learn"]},
    {"title": "Security", "skills": ["sec-cso"]}
  ]
}
```

**LICENSE** — MIT (соответствует garrytan/gstack)

**.github/workflows/validate-skills.yml** — простой CI: для каждого SKILL.md проверяет наличие frontmatter, обязательных полей `name`/`description`, что description ≤ 1024 chars, размер файла ≤ 100k chars (по `~/.hermes/hermes-agent/tools/skill_manager_tool.py::_validate_frontmatter`).

**.gitignore** — стандартный python+macos

**scripts/gstack-to-hermes.py** — для re-translation при обновлении upstream gstack

## Stage 5 — Sanitization preflight

Перед `git push` прогнать чек-лист (из исследования Phase 1, в репо как `scripts/sanity-check.sh`):
- `grep -ri "frankfurt\|aisy-de\|h3cloud\|mymac\|veeskelaam\|/Users/iam\|/home/iam\|91\.188\.213\|43\.131\.58\|72\.56\.89\|claude-all session"` — должно быть пусто
- README.md строка про mutagen sync — переписать generic
- Проверить что `pipeline-record.sh` и `pipeline-state` (если копируем) не содержат `~/.claude/state/` (заменить на `${HERMES_STATE:-~/.hermes/state}/pipeline.json`)

## Stage 6 — Публикация и подключение

1. `cd ~/work/gstack-hermes && git init && git add . && git commit -m "Initial: 8 gstack skills adapted for Hermes Agent"`
2. `gh repo create veeskelad/gstack-hermes --public --source=. --remote=origin --push`
3. На frankfurt:
   ```
   ssh frankfurt "hermes skills tap add veeskelad/gstack-hermes"
   ssh frankfurt "hermes skills install veeskelad/gstack-hermes/yc-office-hours"
   # ...для всех 8
   ```
4. Скопировать hook:
   ```
   scp -r ~/work/gstack-hermes/hooks/pipeline-next-step frankfurt:/home/iam/.hermes/hooks/
   ```
5. Зарегистрировать accept-hooks в `~/.hermes/config.yaml` если ещё не стоит `hooks_auto_accept: true`

## Stage 7 — Hermes update

1. `ssh frankfurt "hermes upgrade --help"` — проверить наличие команды
2. Если есть: `ssh frankfurt "sudo systemctl stop hermes && hermes upgrade && sudo systemctl start hermes"`
3. Если нет — manual:
   ```
   ssh frankfurt "
     sudo systemctl stop hermes
     cp /home/iam/.hermes/config.yaml /home/iam/.hermes/config.yaml.backup-$(date +%s)
     cp /home/iam/.hermes/state.db /home/iam/.hermes/state.db.backup-$(date +%s)
     cd /home/iam/.hermes/hermes-agent
     git pull origin main
     /home/iam/.hermes/hermes-agent/venv/bin/pip install -e .
     sudo systemctl start hermes
   "
   ```
4. Проверить migration logs: `ssh frankfurt "journalctl -u hermes -n 100 --no-pager"`

## Verification (end-to-end)

1. `ssh frankfurt "hermes --version"` → новее v0.15.1
2. `ssh frankfurt "systemctl is-active hermes"` → active
3. `ssh frankfurt "hermes skills tap list"` → видит `veeskelad/gstack-hermes`
4. `ssh frankfurt "ls ~/.hermes/skills/ | grep -E 'yc-|sec-cso'"` → 8 директорий
5. `ssh frankfurt "cat ~/.hermes/skills/.hub/lock.json | jq '.skills | keys'"` → 8 entries с source=`veeskelad/gstack-hermes`
6. В Telegram-gateway (или CLI): `/yc-office-hours <тестовая идея>` → скилл отрабатывает, задаёт 6 вопросов
7. После завершения: `ssh frankfurt "tail -20 ~/.hermes/memories/MEMORY.md"` → видна секция `### Next Steps (gstack pipeline, ...)` с suggestion `/yc-ceo-review`
8. Лог hook'а: `ssh frankfurt "journalctl -u hermes | grep pipeline-next-step | tail"` → handler срабатывал без ошибок

## Key files

**Источники (read-only, не модифицируются):**
- `~/.claude/plugins/gstack/skills/yc-*/SKILL.md` + side-files
- `~/.claude/plugins/gstack/state/pipeline-config.json`
- `~/.claude/plugins/gstack/scripts/strip-boilerplate.py` (переиспользуется)
- `/home/iam/.hermes/hooks/file-size-guard/{HOOK.yaml, handler.py}` (образец)
- `/home/iam/.hermes/skills/software-development/hermes-agent-skill-authoring/SKILL.md` (конвенция)
- `/home/iam/.hermes/hermes-agent/tools/skill_manager_tool.py` (валидатор frontmatter)

**Создаются в новом репо `~/work/gstack-hermes/`:**
- `skills/<8 имен>/SKILL.md` + side-files
- `hooks/pipeline-next-step/{HOOK.yaml, handler.py, pipeline-config.json}`
- `scripts/gstack-to-hermes.py`, `scripts/sanity-check.sh`
- `skills.sh.json`, `README.md`, `LICENSE`, `.gitignore`
- `.github/workflows/validate-skills.yml`

## Риски и mitigations

- **Hermes update сломает что-то** — backup config.yaml + state.db перед апгрейдом, systemctl rollback готов
- **Скилл не активируется через slash** — в hermes по конвенции `/skill-name`, у нас `/yc-office-hours` плоско → должно работать; fallback — auto-discovery по description (уже хорошие descriptions есть)
- **Hook не срабатывает** — `hooks_auto_accept: true` в config.yaml (требуется), `events: [agent:end]` в HOOK.yaml, async signature правильный (проверено по образцу `file-size-guard`)
- **Утечка PII** — preflight sanity-check.sh + manual grep перед `git push`
- **veeskelad нет на GitHub** — проверить `gh api users/veeskelad` перед `gh repo create`; если нет — попросить пользователя залогиниться/создать аккаунт
