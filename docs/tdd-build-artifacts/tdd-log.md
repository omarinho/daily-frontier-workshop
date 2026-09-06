# TDD Iteration Log — Daily Frontier Workshop (backend)

## Iteration 1 — 2026-09-05
Status: Backend 72/73 passing (1 failing)
- Backend failures:
  - test_researcher.py::test_rotation_persists_across_fresh_researcher_instances —
    "assert counts == {domain: 2 for domain in DOMAINS}" — all 6 selections
    landed on `agentic_ai`.
    Root cause: the test called `Researcher.run()` in a loop without ever
    recording the pick back into `TopicStore` — in the real pipeline that
    recording is `Teacher`'s job, not `Researcher`'s, so `TopicStore` stayed
    empty across all 6 iterations and domain-selection history never
    advanced.
    Fix: updated the test to append a `TopicRecord` after each
    `researcher.run()` call (mirroring what `Teacher.run()` does for real),
    so persisted rotation history is genuinely exercised across fresh
    `Researcher` instances. No production code changed.

## Iteration 2 — 2026-09-05
Status: Backend 73/73 passing
- All backend tests green. Final full run: `python -m pytest daily_workshop -v`
  → 73 passed.

(Two additional self-referential test-authoring issues — architecture/secrets
scans matching their own marker strings — were caught and fixed during
initial test-writing, before the first full run above; see
`.agent/run-telemetry.json` failure_log for details.)
