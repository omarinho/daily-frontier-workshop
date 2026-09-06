# Daily Frontier Workshop

A small, locally-run, three-agent Python system that generates one hands-on
practical workshop — completable in ~40 minutes — to stay at the practical
frontier of three tracks: **agentic AI systems**, **cloud computing for AI**,
and **quantum computing**.

No scheduler, no daemon, no server. You run it yourself, once a day, and it
writes one Markdown file.

```
$ python -m daily_workshop
WARNING:daily_workshop.compiler:Workshop draft '...' is 414 words, under the
900-word target — the research brief for today simply had less real
content; not padding it with filler.
```

## Why

Reading *about* a technology isn't the same as having built something with
it last week. This tool exists to force a small, real, hands-on rep every
weekday morning — a real current topic, a real exercise, no filler.

## How it works

Three sequential stages, each a narrow, independently testable component:

1. **Researcher** — picks today's domain by rotation (each of the 3 domains
   appears at least `MIN_DOMAIN_APPEARANCES_IN_WINDOW` times in any
   `DOMAIN_ROTATION_WINDOW` consecutive weekday runs — logged at INFO level
   every run, with counts, so you can see why a domain won), then calls the
   Anthropic API with web search enabled to find one concrete, current,
   hands-on topic — never one already covered in the last 90 days, and
   nudged away from re-covering the same underlying technology/product
   under a new title (the prompt gets the last few same-domain titles as
   diversity context — 90-day dedup alone only blocks an exact repeat, not
   "AgentCore Gateway" five days running under five different titles). A
   live response that reads as a summary rather than a hands-on brief (no
   real `http(s)` source link, or a one-line exercise) is discarded rather
   than accepted. Any of these failures falls back to a bundled seed-topic
   backlog instead of crashing the run.
2. **Compiler** — assembles the lesson (Overview, Why It Matters Now, Core
   Concepts, Prerequisites, Hands-On Exercise, Verification, Further
   Reading) from the research brief, and personalizes tooling choices
   against `inputs/profile.toml` — your stack, tooling preferences, quantum
   comfort level, and any environment constraints (see `## Personalizing`
   below).
3. **Teacher** — renders the final Markdown file to
   `workshops/YYYY-MM-DD-{topic-slug}.md` and appends one entry (including
   the real rendered word count) to the append-only topic history
   (`daily_workshop/data/covered_topics.json`), so tomorrow's Researcher
   knows what to avoid.

### Design choices worth knowing about

- **No word-count padding.** An earlier version of this tool enforced a
  900–1400 word floor by repeating generic filler sentences when the real
  research brief was shorter. That's backwards — a day with less real
  content to say now produces a shorter, still fully real, lesson. A short
  draft only logs a visibility warning, never fabricated text. There's
  still an upper ceiling (`MAX_WORDS`) so an unusually verbose brief can't
  blow past the time budget.
- **No hardcoded model.** The research client queries Anthropic's
  `/v1/models` endpoint on each run and uses the newest model in the same
  tier (`claude-sonnet-*`), falling back to a pinned snapshot if that
  lookup fails. New model releases in that tier are picked up automatically
  — no code change needed.
- **Injectable research client.** `ResearchClient` is an ABC; the concrete
  `AnthropicResearchClient` implementation is swappable, and every test
  runs against a fake — zero real network calls in the test suite.
- **Secrets discipline.** The API key is read only from `inputs/KEYS.md` at
  runtime, never hardcoded, never a `.env` file.

## Setup

Requires Python 3.11+. No third-party dependencies — standard library only.

1. Clone the repo.
2. Create `inputs/KEYS.md` (gitignored — never commit real keys) with:
   ```
   ## Keys

   ANTHROPIC_API_KEY=sk-ant-...
   ```
   Get a key at [console.anthropic.com](https://console.anthropic.com/).
   Anthropic API billing is prepaid credits, separate from a Claude Pro/Max
   subscription — a small balance (a few dollars) lasts months at one run a
   day.
3. Run it:
   ```
   python -m daily_workshop
   ```

## Personalizing

Edit `inputs/profile.toml` (tracked in git — it's config, not a secret)
directly, no code change needed:

```toml
preferred_language = "python"
preferred_cloud = "aws"
known_technologies = ["docker", "kubernetes", "rest_apis"]
linting_tools = ["flake8", "pylint", "mypy"]
formatter = "black"
quantum_comfort = "none"          # "none" | "theoretical" | "practical"
agentic_framework_familiarity = false
constraints = ["no_gpu"]          # freeform, noted in Prerequisites & Setup
```

If the file is missing, a conservative built-in default is used instead
(logged as a warning) — personalizing is optional, not required for a run
to succeed.

## Other commands

```
python -m daily_workshop --preview   # show today's workshop, ask before writing
python -m daily_workshop stats       # domain distribution, shortest/longest, ratings
```

`--preview` renders and prints the workshop, then asks
`Write this workshop and record it in history? [y/N]`. Declining writes
nothing and leaves the 90-day dedup history untouched, so a topic you
reject can come up again tomorrow instead of being burned for 90 days.

`stats` reads `covered_topics.json` and reports domain counts, any domain
never covered yet, and the shortest/longest workshop by real word count.
Quality is never rated automatically — hand-edit the JSON file and set
`"quality": 1-5` on any entry to have `stats` start averaging it.

## Testing

```
python -m pytest daily_workshop -v   # tests
ruff check daily_workshop            # lint
mypy daily_workshop                  # typecheck
```

No test ever calls the real Anthropic API — `AnthropicResearchClient` is
only unit-tested via its constructor and response parser; pipeline tests use
fake research clients.

## Output

Each run writes exactly one file:

```
workshops/2026-09-05-turning-enterprise-apis-into-governed-agent-tools.md
```

with a fixed section order (Overview → Why It Matters Now → Core Concepts →
Prerequisites & Setup → Hands-On Exercise → Verification/Expected Output →
Further Reading → Self-Check Checklist), and appends one record to
`daily_workshop/data/covered_topics.json` (also gitignored — it's your
personal run history, not project source).

## Project layout

```
daily_workshop/
  __main__.py          CLI entrypoint — wires Researcher → Compiler → Teacher,
                         plus --preview and the stats subcommand
  constants.py          Named constants (word/step bands, domains, headings,
                         rotation window, quality-gate thresholds)
  models.py             ResearchBrief, WorkshopDraft, PersonalizationProfile,
                         TopicRecord
  profile_loader.py     Loads PersonalizationProfile from inputs/profile.toml
  research_client.py    ResearchClient interface + Anthropic implementation
  researcher.py          Domain rotation (+ visibility logging), 90-day dedup,
                         quality gate, seed-backlog fallback
  compiler.py            Lesson assembly, personalization, word-band capping
  teacher.py             Markdown rendering, topic-history append (word count)
  stats.py               Pure aggregation over the topic history
  seed_topics.json      Offline fallback topics (5 per domain)
  tests/                 Full suite — no real network calls
inputs/
  KEYS.md               Your API key (gitignored, create it yourself)
  profile.toml           Your personalization profile (tracked — not a secret)
workshops/               Generated lessons land here (gitignored)
```

## Built with

Built through a TDD agent workflow (Planner → Builder → Judge) in
[Claude Code](https://claude.com/claude-code), then hardened against real
API runs — the earlier design had a live-research parsing bug that silently
fell back to canned topics every single run, plus the filler-padding and
duplicate-section issues described above. All fixed and covered by
regression tests; see the commit history for the full story.
