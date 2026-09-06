"""Typed value objects passed between Researcher, Compiler, and Teacher.

Researcher, Compiler, and Teacher never import each other directly — they
communicate only through these dataclasses, wired together in
``daily_workshop/__main__.py``. See
``inputs/code-style-guides/backend.md`` "Architecture Pattern".
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ResearchBrief:
    """One researched, hands-on-capable topic for a single domain."""

    domain: str
    title: str
    slug: str
    rationale: str
    key_facts: tuple[str, ...]
    source_links: tuple[str, ...]
    exercise_idea: str


@dataclass(frozen=True)
class TopicRecord:
    """One append-only entry in the covered-topics history (AC8).

    ``word_count`` is filled in automatically by Teacher (the real rendered
    length). ``quality`` is never written by the pipeline — it stays
    ``None`` unless you hand-edit ``covered_topics.json`` to add a 1-5
    rating; ``python -m daily_workshop stats`` picks it up if present.
    """

    date: date
    domain: str
    slug: str
    summary: str
    word_count: int = 0
    quality: int | None = None


@dataclass
class WorkshopDraft:
    """The Compiler's output: content ready for Teacher to format and write.

    Mutable (unlike the frozen value objects above) because the Compiler
    trims/expands it in place while enforcing the word/step budget (AC7).
    """

    title: str
    domain: str
    slug: str
    sections: dict[str, str]
    hands_on_steps: list[str]
    self_check_items: list[str]


@dataclass(frozen=True)
class PersonalizationProfile:
    """Learner-specific rules the Compiler consults (AC11).

    Loaded from ``inputs/profile.toml`` by
    :func:`daily_workshop.profile_loader.load_personalization_profile` — a
    clone with a different learner, or the same learner adopting a new
    stack, is a one-file edit, never a code change.
    """

    preferred_language: str
    preferred_cloud: str
    known_technologies: tuple[str, ...]
    linting_tools: tuple[str, ...]
    formatter: str
    # One of "none" | "theoretical" | "practical" — how much quantum-track
    # workshops can assume the learner already knows.
    quantum_comfort: str
    agentic_framework_familiarity: bool
    # Freeform tags (e.g. "no_gpu", "local_only") noted in Prerequisites &
    # Setup — informational only, never fed back into what topic/exercise
    # gets researched.
    constraints: tuple[str, ...] = ()
