"""Named constants shared across the Daily Frontier Workshop pipeline.

Every bound referenced by more than one module (word-count band, hands-on
step band, topic-dedup cooldown, ...) is defined exactly once here and
imported everywhere else. Do not inline these values — see
``inputs/code-style-guides/backend.md`` "Anti-Patterns to Avoid".
"""

from __future__ import annotations

# ─── Time budget (AC7) ──────────────────────────────────────────────────────
# MAX_WORDS is a hard ceiling (Compiler trims to it) so a single verbose
# research brief can't blow past the 40-minute budget. MIN_WORDS is a soft
# floor used only to flag a short brief (Compiler logs a warning) — never to
# pad real content with fabricated filler. A day with genuinely less to say
# should produce a shorter, still fully real, lesson rather than an inflated
# one.
TARGET_MINUTES: int = 40
MIN_WORDS: int = 900
MAX_WORDS: int = 1400
MIN_STEPS: int = 4
MAX_STEPS: int = 8

# ─── Research brief shape (REQ-012) ────────────────────────────────────────
MIN_KEY_FACTS: int = 3
MAX_KEY_FACTS: int = 5

# ─── Research brief quality gate ───────────────────────────────────────────
# A live ResearchClient response below this bar (a one-line exercise, or no
# real http(s) source link) reads as a summary, not a hands-on brief — the
# Researcher discards it and falls back to the seed backlog rather than
# accepting a technically-present-but-thin response.
MIN_EXERCISE_WORDS: int = 8

# ─── Topic dedup (AC4) ──────────────────────────────────────────────────────
TOPIC_COOLDOWN_DAYS: int = 90

# ─── Topical diversity within a domain ─────────────────────────────────────
# Slug-based 90-day dedup (AC4) only blocks an exact repeat topic — it does
# nothing about live research returning the same underlying
# technology/product reframed under a new title every time it's the hottest
# thing in a domain (observed in practice: several real runs in a row all
# being some angle on "Amazon Bedrock AgentCore + MCP"). Researcher passes
# the last this-many same-domain titles to the research prompt so the model
# can judge "different angle on the same thing" itself, rather than us
# trying to detect topic clusters mechanically.
RECENT_TITLES_CONTEXT_WINDOW: int = 5

# ─── Domain rotation fairness (AC3) — configurable, logged for visibility ──
# select_domain()'s greedy least-selected-so-far rule (using the *entire*
# history, not just this window) already guarantees each domain is at least
# this well represented in any window of this size — these constants don't
# change that algorithm, they name the policy it satisfies so Researcher can
# log it and a reader can see what's being enforced instead of a bare "4"
# and "15" floating in a docstring.
DOMAIN_ROTATION_WINDOW: int = 15
MIN_DOMAIN_APPEARANCES_IN_WINDOW: int = 4

# ─── Domains (AC3) ──────────────────────────────────────────────────────────
DOMAIN_AGENTIC_AI: str = "agentic_ai"
DOMAIN_CLOUD_COMPUTING: str = "cloud_computing"
DOMAIN_QUANTUM_COMPUTING: str = "quantum_computing"
DOMAINS: tuple[str, ...] = (
    DOMAIN_AGENTIC_AI,
    DOMAIN_CLOUD_COMPUTING,
    DOMAIN_QUANTUM_COMPUTING,
)

# ─── Fixed Markdown section order (AC6) ─────────────────────────────────────
HEADING_OVERVIEW: str = "Overview"
HEADING_WHY_IT_MATTERS_NOW: str = "Why It Matters Now"
HEADING_CORE_CONCEPTS: str = "Core Concepts"
HEADING_PREREQUISITES: str = "Prerequisites & Setup"
HEADING_HANDS_ON_EXERCISE: str = "Hands-On Exercise"
HEADING_VERIFICATION: str = "Verification / Expected Output"
HEADING_FURTHER_READING: str = "Further Reading"
HEADING_SELF_CHECK: str = "Self-Check Checklist"

REQUIRED_HEADINGS: tuple[str, ...] = (
    HEADING_OVERVIEW,
    HEADING_WHY_IT_MATTERS_NOW,
    HEADING_CORE_CONCEPTS,
    HEADING_PREREQUISITES,
    HEADING_HANDS_ON_EXERCISE,
    HEADING_VERIFICATION,
    HEADING_FURTHER_READING,
    HEADING_SELF_CHECK,
)
