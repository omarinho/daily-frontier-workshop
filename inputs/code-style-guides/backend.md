# Backend Style Guide — Daily Frontier Workshop

> **Stack:** Python 3.11+, pytest, ruff, black

Configures `CONFIG.codebase.backend` for the Daily Frontier Workshop project
(see `../INSTRUCTIONS.md`). This is the only active module — `frontend` and
`api` are `null` for this project; there is no UI and no HTTP surface.

## Technology Overview

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| Test framework | pytest |
| Linter | ruff |
| Formatter | black |
| Type checking | mypy (strict on new modules) |
| Data validation | `dataclasses` for internal value objects; `pydantic` only if/when external (LLM/API) JSON needs schema validation |
| CLI | thin entrypoint module only — no framework needed (argparse if flags are ever needed) |

These match Omar's own stated tooling preferences (PyCharm, PEP 8, Flake8/
Pylint/Mypy, Black — see `../attachments/linkedin-profile-omar-marino.md`);
ruff subsumes Flake8/Pylint rule coverage for this project, run alongside mypy.

## Architecture Pattern

Three agent classes, one per pipeline stage, each with a single public method
and no hidden shared state:

```
daily_workshop/
  researcher.py   # Researcher.run(state) -> ResearchBrief
  compiler.py      # Compiler.run(brief) -> WorkshopDraft
  teacher.py       # Teacher.run(draft) -> Path (file written)
  models.py        # dataclasses: ResearchBrief, WorkshopDraft, TopicRecord
  topic_store.py   # TopicStore: read/append covered-topics history (append-only)
  research_client.py  # ResearchClient protocol + concrete + fake implementations
  seed_topics.json # bundled backlog, keyed by domain
  __main__.py      # wires Researcher -> Compiler -> Teacher, nothing else
```

- **Dependency injection over globals.** `Researcher` takes a `ResearchClient`
  and a `TopicStore` as constructor arguments — never imports a concrete network
  client directly. This is what makes AC3/AC4/AC5 unit-testable without network
  access.
- **Repository-pattern-lite for persistence.** All reads/writes to
  `covered_topics.json` (or wherever `TopicStore` lives) go through the
  `TopicStore` class. No other module touches that file directly.
- **Pure functions for budget/format logic.** Word-count banding (AC7) and
  section-order rendering (AC6) should be pure functions of a `WorkshopDraft` —
  no I/O, no randomness — so they're trivial to unit test.
- **`__main__.py` stays thin.** It only constructs the three agents and calls
  them in order; no business logic lives there.

## Naming Conventions

- `snake_case` for functions, methods, variables, and module names.
- `PascalCase` for classes (`Researcher`, `TopicStore`, `ResearchBrief`).
- Constants in `UPPER_SNAKE_CASE` at module scope (e.g. `TARGET_MINUTES = 40`,
  `MIN_WORDS = 900`, `MAX_WORDS = 1400`, `TOPIC_COOLDOWN_DAYS = 90`) — never
  inline magic numbers for these values; AC7 and AC4 depend on named constants.
- Test files: `test_<module>.py`, mirroring the module under test one-to-one.
- Fakes/mocks for `ResearchClient` live in `tests/fakes.py`, named
  `FakeResearchClient`, `FailingResearchClient`, etc. — not inline lambdas
  scattered across test files.

## Type Hints & Data Modeling

- Every function signature is fully typed — no bare `def f(x):`.
- No `Any` unless wrapping a genuinely untyped third-party return (and even
  then, narrow it with a local `TypedDict` or cast at the boundary).
- Use `@dataclass(frozen=True)` for value objects that don't change after
  construction (`ResearchBrief`, `TopicRecord`). Use a plain mutable
  `@dataclass` only for the in-progress `WorkshopDraft` while the Compiler is
  trimming/expanding it.
- Dates are always `datetime.date`, never bare strings, until the moment
  they're serialized to JSON/Markdown.

## Testing

- Arrange-Act-Assert structure in every test; one behavior per test function.
- No test may perform a real network call — all `ResearchClient` usage in tests
  is a fake/fixture. This is a hard rule, not a style preference (AC3/AC4/AC5
  are meaningless if tests hit the network).
- Use `tmp_path` (pytest fixture) for any test that touches `TopicStore` or
  writes a workshop file — never write to the real `workshops/` directory or
  the real covered-topics store from a test.
- Prefer table-driven tests (`@pytest.mark.parametrize`) for the word-count band
  and domain-rotation checks rather than one test per boundary value.

## Anti-Patterns to Avoid

- Do not let the Researcher, Compiler, or Teacher import each other directly —
  they communicate only through the typed dataclasses in `models.py`, wired
  together in `__main__.py`.
- Do not hardcode `TARGET_MINUTES`, word-count bounds, or the 90-day cooldown
  inline in multiple places — define once, import everywhere.
- Do not swallow a `ResearchClient` failure silently — the fallback to
  `seed_topics.json` must be an explicit, logged branch, not a bare
  `except: pass`.
- Do not write covered-topics history by re-serializing the entire file with
  a modified in-memory list unless the store's own class does it atomically
  (write-temp-then-rename) — a crash mid-write must never corrupt prior history
  (AC8 is append-only *and* durable).
- Do not put the workshop's own topic-history file under the repo's `memory/`
  directory — that path is reserved for this TDD framework's own knowledge
  base (see `../INSTRUCTIONS.md` "Additional Notes").
- Do not add a scheduler, cron entry, or background service anywhere in this
  codebase (AC9) — if you find yourself reaching for `schedule`, `APScheduler`,
  or a systemd unit file, stop; that's out of scope by design.
