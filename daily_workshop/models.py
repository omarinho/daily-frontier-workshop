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
    """One append-only entry in the covered-topics history (AC8)."""

    date: date
    domain: str
    slug: str
    summary: str


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
    """Static, learner-specific rules the Compiler consults (AC11).

    Set once from the learner's own background (stack, tooling preferences,
    what to assume they already know) and refreshed manually — not parsed
    from any external profile source at runtime.
    """

    preferred_language: str
    preferred_cloud: str
    known_technologies: tuple[str, ...]
    linting_tools: tuple[str, ...]
    formatter: str
    quantum_background: bool
    agentic_framework_familiarity: bool
