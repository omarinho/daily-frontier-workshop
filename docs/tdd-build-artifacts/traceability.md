# Traceability Matrix — Daily Frontier Workshop

**Phase 0 result:** `frontend_active = false` — `inputs/code-style-guides/frontend.md` does not
exist (only `README.md` and `backend.md` are present in `inputs/code-style-guides/`), and
`CONFIG.md` has `codebase.frontend: null`, `codebase.api: null`. All Frontend/Figma steps in
Phases 3-9 are no-ops for this run. No Figma links appear anywhere in `inputs/INSTRUCTIONS.md`.

**Active module:** `backend` only (`./daily_workshop`).

| REQ-ID | Title | Module | Test Type | Test File | Status |
|--------|-------|--------|-----------|-----------|--------|
| REQ-001 | Single CLI entrypoint runs the full pipeline | backend | Integration | daily_workshop/tests/test_cli.py | COVERED |
| REQ-002 | Deterministic output location, no silent clobber | backend | Integration | daily_workshop/tests/test_teacher.py | COVERED |
| REQ-003 | Domain rotation fairness across 15 runs | backend | Unit | daily_workshop/tests/test_researcher.py | COVERED |
| REQ-004 | 90-day topic dedup | backend | Unit | daily_workshop/tests/test_researcher.py | COVERED |
| REQ-005 | Seed-topic backlog fallback on research failure | backend | Unit | daily_workshop/tests/test_researcher.py | COVERED |
| REQ-006 | Fixed Markdown section order | backend | Unit | daily_workshop/tests/test_teacher.py | COVERED |
| REQ-007 | Time-budget enforcement (word count + step count) | backend | Unit | daily_workshop/tests/test_compiler.py | COVERED |
| REQ-008 | Append-only, durable covered-topics history | backend | Unit | daily_workshop/tests/test_topic_store.py | COVERED |
| REQ-009 | No scheduler/daemon integration | backend | Static/Unit | daily_workshop/tests/test_architecture.py | COVERED |
| REQ-010 | Secrets discipline for research API key | backend | Unit | daily_workshop/tests/test_research_client.py | COVERED |
| REQ-011 | Personalization applied from LinkedIn profile | backend | Unit | daily_workshop/tests/test_compiler.py | COVERED |
| REQ-012 | Research brief structure [inferred] | backend | Unit | daily_workshop/tests/test_researcher.py | COVERED* |
| REQ-013 | Seed topic backlog minimum content [inferred] | backend | Unit | daily_workshop/tests/test_seed_topics.py | COVERED |

> `*` REQ-012: all 73 planned tests pass (test-coverage mapping is complete), but
> JudgeAgent's Phase 9 correctness audit (implementation vs. requirements, not
> tests) found a genuine gap the test suite doesn't probe: seed-backlog entries
> with empty `source_links` can produce a `ResearchBrief` violating this
> requirement's "at least one source link" criterion. See
> `.agent/correctness-audit.json` and `.agent/remediation-plan.json`. Traceability
> (test mapping) and correctness (behavior vs. intent) are separate checks by
> design — this row reflects the former; the latter is `NEEDS_REMEDIATION`.

## Categorization

- **By module:** all 13 requirements are `backend` — no `frontend`/`api` requirements exist.
- **By type:** REQ-001..008, REQ-010..013 = `functional`; REQ-009 = `architecture` (a negative/constraint
  check enforced by static inspection rather than behavioral assertion).

## Codebase mapping (existing vs. new)

`./daily_workshop` does not exist yet — this is a greenfield module. Per `inputs/code-style-guides/backend.md`,
BuilderAgent will create:

```
daily_workshop/
  __main__.py           # NEW - wires Researcher -> Compiler -> Teacher (REQ-001)
  researcher.py         # NEW - REQ-003, REQ-004, REQ-005, REQ-012
  compiler.py            # NEW - REQ-007, REQ-011
  teacher.py             # NEW - REQ-002, REQ-006
  models.py              # NEW - ResearchBrief, WorkshopDraft, TopicRecord (REQ-012)
  topic_store.py         # NEW - REQ-008
  research_client.py     # NEW - ResearchClient protocol + concrete + fake (REQ-005, REQ-010)
  seed_topics.json        # NEW - REQ-013
  data/
    covered_topics.json  # NEW - runtime-created by TopicStore, not committed with content (REQ-004, REQ-008)
  tests/
    fakes.py             # NEW - FakeResearchClient, FailingResearchClient (per backend.md)
    test_cli.py            # NEW
    test_researcher.py     # NEW
    test_compiler.py       # NEW
    test_teacher.py         # NEW
    test_topic_store.py    # NEW
    test_research_client.py# NEW
    test_seed_topics.py    # NEW
    test_architecture.py   # NEW
workshops/                 # NEW at repo root - Teacher's output directory (REQ-002)
```

No files are modified (nothing pre-exists under `./daily_workshop`).

## Figma / visual requirements

None. `figma_sources` is empty; no requirement carries `figma_refs`. Phase 8 (JudgeAgent) will
be a no-op for this run per `inputs/INSTRUCTIONS.md`'s "Design References (Figma)" section.

## `app_url` gate check

N/A — no visual requirements exist, so the "no requirement has `app_url: null`" gate is
trivially satisfied (there are zero Figma refs to resolve).
