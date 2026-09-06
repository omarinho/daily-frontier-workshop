# Test Plan — Daily Frontier Workshop

`frontend_active = false`. No image attachments, no parent/linked JIRA tickets, no Figma
designs exist for this task, so the Phase 3 Step 2a mandatory source-inventory
cross-reference gate does not apply (its trigger condition — "if any of the following exist:
image attachments, parent/linked tickets, or Figma designs" — is false). The sole requirement
source is `inputs/INSTRUCTIONS.md` (Task Description + AC1-AC11 + Additional Notes) plus the
two supporting docs (`backend.md`, `linkedin-profile-omar-marino.md`), all fully read in
Phase 1. Frontend test-plan steps (Layer 1/Layer 2 Playwright, `toHaveScreenshot()` baselines,
`boundingBox()` positional rules) are no-ops — this is a backend-only CLI tool.

All tests are backend (pytest), per `CONFIG.md` (`tests.backend.unit: pytest`,
`tests.backend.integration: pytest` — no separate integration runner). All `ResearchClient`
usage in tests is a fake (`daily_workshop/tests/fakes.py`), per `backend.md` — no test may
perform a real network call.

---

## REQ-001 — Single CLI entrypoint runs the full pipeline (AC1)

```
REQ-001: Single CLI entrypoint runs RESEARCHER -> COMPILER -> TEACHER
├── Happy path
│   └── TC-001-01: Entrypoint invoked with fake ResearchClient + tmp_path TopicStore/workshops
│                  dir runs all three stages in order and exits 0
├── Ordering
│   └── TC-001-02: A call-order spy proves Researcher runs before Compiler before Teacher
└── Failure path [inferred]
    └── TC-001-03: If Teacher raises (e.g. disk write error), entrypoint exits non-zero,
                   not 0
```

## REQ-002 — Deterministic output location, no silent clobber (AC2)

```
REQ-002: workshops/YYYY-MM-DD-{slug}.md, one new file, no clobber
├── TC-002-01: Successful run writes exactly one new file at
│              workshops/{today}-{slug}.md (tmp_path-based)
├── TC-002-02: Second run same calendar day either (a) skips with a clear message, or
│              (b) writes a disambiguated filename — either way, first file's bytes are
│              unchanged after the second run
└── TC-002-03: Filename slug is a normalized, deterministic transform of the topic title
               (e.g. lowercase, hyphen-separated, no special characters)
```

## REQ-003 — Domain rotation fairness across 15 runs (AC3)

```
REQ-003: Rotation guarantees >=4 selections per domain over 15 runs
├── TC-003-01: 15 simulated consecutive weekday runs with injected/fake rotation state
│              (no network) -> each of the 3 domains selected >= 4 times
├── TC-003-02: Rotation state persists across calls (a fresh Researcher instance reading
│              the same injected state continues the rotation correctly)
└── TC-003-03: Parametrized/table-driven variant confirms no domain is ever skipped for
               more than N consecutive runs (guards "no domain dominates indefinitely")
```

## REQ-004 — 90-day topic dedup (AC4)

```
REQ-004: Never re-select a slug covered within 90 days
├── TC-004-01: Fixture store has slug dated 10 days ago -> excluded from candidates
├── TC-004-02 [inferred]: Fixture store has slug dated 91 days ago -> eligible again
└── TC-004-03 [inferred]: Fixture store has slug dated exactly TOPIC_COOLDOWN_DAYS ago ->
               boundary behavior is explicit (documented as inclusive or exclusive) and
               asserted by the test, not left ambiguous
```

## REQ-005 — Seed-topic backlog fallback (AC5)

```
REQ-005: Fallback to seed_topics.json on ResearchClient failure
├── TC-005-01: Injected ResearchClient (FailingResearchClient) raises -> Researcher
│              completes by returning a brief built from the next unused seed_topics.json
│              entry, no unhandled exception propagates
├── TC-005-02: Injected ResearchClient returns None/empty -> same fallback path taken
├── TC-005-03: Fallback branch is explicit/logged (assert a log record or explicit
│              result flag such as `brief.source == "fallback"`) — not a bare except: pass
└── TC-005-04 [inferred]: Fallback also excludes seed topics already covered within the
               90-day window (composes with REQ-004's TopicStore check)
```

## REQ-006 — Fixed Markdown section order (AC6)

```
REQ-006: 8 headings, exact order
├── TC-006-01: Rendered document's headings, extracted in document order, equal exactly:
│              ["Overview", "Why It Matters Now", "Core Concepts", "Prerequisites & Setup",
│               "Hands-On Exercise", "Verification / Expected Output", "Further Reading",
│               "Self-Check Checklist"]
│              (exact string match per heading — never a substring/`in` check alone)
└── TC-006-02: A draft missing one required section (e.g. no "Further Reading") fails the
               structure validation before Teacher writes the file
```

## REQ-007 — Time-budget enforcement (AC7)

```
REQ-007: word count in [MIN_WORDS, MAX_WORDS]=[900,1400], steps in [4,8]
├── Word count (parametrized/table-driven)
│   ├── TC-007-01: Draft at 1100 words (inside band) -> written unchanged in length
│   ├── TC-007-02: Draft at 500 words (below MIN_WORDS) -> expanded; final count in band
│   └── TC-007-03: Draft at 2000 words (above MAX_WORDS) -> trimmed; final count in band
├── Step count (parametrized/table-driven)
│   ├── TC-007-04: Exercise with 3 steps -> expanded/padded to >= 4 numbered steps
│   ├── TC-007-05: Exercise with 4 and with 8 steps -> both pass unchanged (boundaries)
│   └── TC-007-06: Exercise with 9 steps -> trimmed/consolidated to <= 8 numbered steps
└── Constants
    └── TC-007-07: MIN_WORDS, MAX_WORDS, MIN_STEPS, MAX_STEPS are imported module-level
                   constants (test imports them by name from the module; no hardcoded
                   duplicate literals accepted in the assertion targets)
```

## REQ-008 — Append-only, durable covered-topics history (AC8)

```
REQ-008: Append-only + atomic write
├── TC-008-01: After a run, store has exactly one new well-formed entry
│              (date, domain, topic_slug, summary) and all prior entries are
│              byte-for-byte identical to their pre-run bytes
└── TC-008-02 [inferred]: Simulated failure between temp-file write and rename
               (e.g. monkeypatch os.replace to raise) leaves the original file's bytes
               untouched and still containing only its prior entries
```

## REQ-009 — No scheduler/daemon integration (AC9)

```
REQ-009: static/negative checks
├── TC-009-01: Recursive scan of daily_workshop/ source files contains no import of
│              `schedule`, `apscheduler`, `crontab`, or similar scheduler packages
├── TC-009-02: No cron/systemd-unit/Task-Scheduler config files exist anywhere in the
│              repository under daily_workshop/ or workshops/
└── TC-009-03 [inferred]: __main__.py contains no `while True` / polling-loop / daemon
               construct — the entrypoint runs once and returns
```

## REQ-010 — Secrets discipline for research API key (AC10)

```
REQ-010: KEYS.md-only secret sourcing
├── TC-010-01: Concrete ResearchClient reads its API key exclusively via a KEYS.md
│              parser (test injects a temp KEYS.md with a fake key and asserts it is
│              picked up; no hardcoded literal key exists in source)
├── TC-010-02: Static scan of daily_workshop/ contains no `.env` usage
│              (no python-dotenv import, no os.environ read for the key outside the
│              KEYS.md-loading path)
└── TC-010-03 [inferred]: Missing/empty key in KEYS.md -> client raises a clear,
               typed configuration error at construction time (not a silent fallback)
```

## REQ-011 — Personalization applied from LinkedIn profile (AC11)

```
REQ-011: Personalization rule consulted (not prose-matched)
├── TC-011-01: Compiler is constructed with a PersonalizationProfile loaded from
│              linkedin-profile-omar-marino.md-derived data; test asserts the profile
│              object's fields (e.g. preferred_language="python",
│              preferred_cloud="aws") are read during Compiler.run()
├── TC-011-02: For a cloud-computing-domain brief, Compiler's render context receives
│              cloud="aws" sourced from the profile (assert the field/rule consulted,
│              not the literal generated prose)
└── TC-011-03 [inferred]: For a brief whose exercise touches REST/Docker/Kubernetes,
               Compiler's "assume senior fluency" suppression branch is exercised
               (assert a skip-basics flag was set to True), not asserted via prose diff
```

## REQ-012 — Research brief structure [inferred]

```
REQ-012: ResearchBrief required fields
├── TC-012-01: A completed ResearchBrief has non-empty title, rationale, source_links
│              (>=1), exercise_idea, and key_facts
└── TC-012-02: key_facts length is validated/asserted to be within [3, 5]
               (parametrized: 2 -> invalid/padded, 3 -> valid, 5 -> valid, 6 -> invalid/trimmed,
               per whichever enforcement BuilderAgent implements — construction-time
               validation or a normalization step)
```

## REQ-013 — Seed topic backlog minimum content [inferred]

```
REQ-013: seed_topics.json baseline content
├── TC-013-01: Loading seed_topics.json yields >= 5 entries for each of
│              agentic_ai / cloud_computing / quantum_computing
└── TC-013-02: Each entry has a unique normalized slug, a title, and a domain field
```

---

## Source inventory cross-reference (informational — gate not triggered)

```
INSTRUCTIONS.md (Task Description):    3 agents x behaviors  -> REQ-001..002 (Teacher/CLI),
                                        REQ-003..005/012 (Researcher), REQ-007/011 (Compiler)
INSTRUCTIONS.md (AC1-AC11):            11 acceptance criteria -> REQ-001..011 (1:1)
INSTRUCTIONS.md (Additional Notes):    seed backlog + key-storage notes -> REQ-013, REQ-010
backend.md (style/architecture rules): DI, atomic write, no cross-agent imports,
                                        named constants -> folded into REQ-005, REQ-007,
                                        REQ-008, REQ-009 acceptance criteria and into
                                        BuilderAgent implementation notes (traceability.md)
linkedin-profile-omar-marino.md:       personalization rules -> REQ-011
─────────────────────────────────────────────
Total inventory items mapped:          13 requirements, 38 test cases, 0 gaps
```

No Figma frames, no image attachments, no parent/linked tickets exist for this task, so
those inventory rows are correctly absent (not a gap — the gate's trigger condition is false).

## Backend test plan (per `AGENTS-planner.md` Phase 3 Step 3)

- **Unit tests:** pure business logic, no I/O — rotation selection, dedup comparison, word/step
  banding, slug normalization, section-order validation. No `ResearchClient` implementation
  under test may touch the network; only `FakeResearchClient`/`FailingResearchClient` are used.
- **Repository-style tests (TopicStore):** use `tmp_path` per `backend.md` — never write to the
  real `workshops/` directory or a real `covered_topics.json` from a test.
- **"Integration" tests (still no network, per `CONFIG.md` `tests.backend.integration: pytest`):**
  the full `__main__` pipeline wired end-to-end with fakes writing into `tmp_path`.

## API test plan

Not applicable — `CONFIG.codebase.api = null`, no HTTP surface exists in this project.
