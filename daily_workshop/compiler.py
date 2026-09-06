"""Compiler: assembles lesson content and enforces the ~40-minute budget.

Depends only on :class:`ResearchBrief` in, :class:`WorkshopDraft` out — never
imports Researcher or Teacher directly. Word-count banding (AC7) and the
personalization render context (AC11) are pure functions of their inputs, no
I/O, no randomness, so they're trivial to unit test in isolation.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import cast

from daily_workshop.constants import (
    DOMAIN_CLOUD_COMPUTING,
    DOMAIN_QUANTUM_COMPUTING,
    HEADING_CORE_CONCEPTS,
    HEADING_FURTHER_READING,
    HEADING_OVERVIEW,
    HEADING_PREREQUISITES,
    HEADING_VERIFICATION,
    HEADING_WHY_IT_MATTERS_NOW,
    MAX_STEPS,
    MAX_WORDS,
    MIN_STEPS,
    MIN_WORDS,
)
from daily_workshop.models import PersonalizationProfile, ResearchBrief, WorkshopDraft
from daily_workshop.profile_loader import load_personalization_profile

logger = logging.getLogger(__name__)

NARRATIVE_HEADINGS: tuple[str, ...] = (
    HEADING_OVERVIEW,
    HEADING_WHY_IT_MATTERS_NOW,
    HEADING_CORE_CONCEPTS,
    HEADING_PREREQUISITES,
    HEADING_VERIFICATION,
    HEADING_FURTHER_READING,
)

# Technologies senior-fluency suppression applies to (AC11 / REQ-011 — the
# learner's personalization profile says "assume senior-level fluency ... do
# not spend workshop time re-explaining these").
_SUPPRESSIBLE_KEYWORDS: tuple[str, ...] = ("rest", "docker", "kubernetes", "k8s")
_SUPPRESSIBLE_PROFILE_TECHNOLOGIES: tuple[str, ...] = (
    "rest_apis",
    "docker",
    "kubernetes",
)

# Cycled per key fact in _build_core_concepts so elaborated facts read as
# distinct sentences rather than a bare list — real brief content, not
# fabricated detail.
_KEY_FACT_FRAMINGS: tuple[str, ...] = (
    "Key fact: {fact}",
    "In practice, this means: {fact}",
    "Worth remembering: {fact}",
)

_QUANTUM_COMFORT_NOTES: dict[str, str] = {
    "none": (
        " No prior quantum background is assumed — this starts from first "
        "principles on the quantum concept itself."
    ),
    "practical": (
        " Hands-on quantum fluency is assumed here, so first-principles "
        "setup is skipped."
    ),
    # "theoretical" gets no extra note: math/concepts assumed, tooling
    # walkthrough stays as normal.
}


def build_render_context(
    brief: ResearchBrief, profile: PersonalizationProfile
) -> dict[str, object]:
    """Pure function: derive template variables from the brief + profile (AC11)."""
    haystack = f"{brief.title} {brief.rationale} {brief.exercise_idea}".lower()
    mentions_suppressible_topic = any(
        keyword in haystack for keyword in _SUPPRESSIBLE_KEYWORDS
    )
    already_known = any(
        tech in profile.known_technologies
        for tech in _SUPPRESSIBLE_PROFILE_TECHNOLOGIES
    )
    quantum_note = (
        _QUANTUM_COMFORT_NOTES.get(profile.quantum_comfort, "")
        if brief.domain == DOMAIN_QUANTUM_COMPUTING
        else ""
    )
    return {
        "language": profile.preferred_language,
        "cloud": profile.preferred_cloud
        if brief.domain == DOMAIN_CLOUD_COMPUTING
        else None,
        "suppress_known_basics": mentions_suppressible_topic and already_known,
        "quantum_note": quantum_note,
        "constraints": profile.constraints,
    }


def _split_rationale(rationale: str) -> tuple[str, str]:
    """Split a multi-sentence rationale into (hook, rest).

    Overview gets the hook (first sentence); Why It Matters Now gets the
    rest — so a rich, multi-sentence rationale isn't duplicated verbatim
    across both sections. A single-sentence rationale degrades gracefully
    to the same text in both (nothing left to split).
    """
    sentences = re.split(r"(?<=[.!?]) +", rationale.strip())
    if len(sentences) <= 1:
        return rationale, rationale
    return sentences[0], " ".join(sentences[1:])


def _build_core_concepts(key_facts: tuple[str, ...]) -> str:
    """Elaborate each key fact into its own paragraph (real content, not filler).

    Joined with blank lines (not spaces) so Markdown actually renders each
    fact as a separate paragraph instead of one dense wall of text.
    """
    paragraphs = []
    for i, fact in enumerate(key_facts):
        framing = _KEY_FACT_FRAMINGS[i % len(_KEY_FACT_FRAMINGS)]
        sentence = framing.format(fact=fact.rstrip("."))
        paragraphs.append(f"{sentence}.")
    return "\n\n".join(paragraphs)


def enforce_word_band(prose: str, max_words: int = MAX_WORDS) -> str:
    """Cap ``prose`` at ``max_words``; never pad short prose with filler.

    A short brief means a shorter, still fully real, lesson — not an
    inflated one. Only over-length prose gets touched, and only trimmed.
    """
    words = prose.split()
    if len(words) <= max_words:
        return prose
    return " ".join(words[:max_words])


def enforce_step_band(
    steps: list[str], min_steps: int = MIN_STEPS, max_steps: int = MAX_STEPS
) -> list[str]:
    """Return ``steps`` unchanged if within [min_steps, max_steps].

    Otherwise appends generic practice steps up to ``min_steps``, or trims
    trailing steps down to ``max_steps``.
    """
    steps = list(steps)
    if min_steps <= len(steps) <= max_steps:
        return steps
    if len(steps) < min_steps:
        while len(steps) < min_steps:
            steps.append(
                f"Additional practice step {len(steps) + 1}: revisit the "
                f"previous step and extend it with a new variation."
            )
        return steps
    return steps[:max_steps]


def total_word_count(draft: WorkshopDraft) -> int:
    """Prose word count across the narrative sections (excludes step lists)."""
    return sum(len(text.split()) for text in draft.sections.values())


def _trim_to_word_budget(text: str, word_budget: int) -> str:
    """Trim ``text`` (paragraphs separated by blank lines) to ``word_budget`` words.

    Drops whole trailing paragraphs first, so paragraphs that survive keep
    their blank-line breaks intact instead of being flattened back into one
    wall of text. Only splits mid-paragraph if even the first kept
    paragraph alone exceeds the budget.
    """
    if word_budget <= 0:
        return ""
    kept: list[str] = []
    used = 0
    for paragraph in text.split("\n\n"):
        words = paragraph.split()
        if used + len(words) <= word_budget:
            kept.append(paragraph)
            used += len(words)
        else:
            remaining = word_budget - used
            if remaining > 0:
                kept.append(" ".join(words[:remaining]))
            break
    return "\n\n".join(kept)


def finalize_word_count(
    draft: WorkshopDraft, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS
) -> WorkshopDraft:
    """Cap ``draft`` (via its Core Concepts section) at ``max_words``.

    Never pads a short draft — a day with less real content to say produces
    a shorter, still fully real, lesson rather than one inflated with
    filler. ``min_words`` is only used to log a visibility warning.
    """
    count = total_word_count(draft)
    if count < min_words:
        logger.warning(
            "Workshop draft %r is %d words, under the %d-word target — "
            "the research brief for today simply had less real content; "
            "not padding it with filler.",
            draft.slug,
            count,
            min_words,
        )
    if count <= max_words:
        return draft

    sections = dict(draft.sections)
    core = sections.get(HEADING_CORE_CONCEPTS, "")
    overshoot = count - max_words
    core_word_count = sum(len(p.split()) for p in core.split("\n\n"))
    keep = max(core_word_count - overshoot, 0)
    core = _trim_to_word_budget(core, keep)
    sections[HEADING_CORE_CONCEPTS] = core
    return dataclasses.replace(draft, sections=sections)


def finalize_step_count(
    draft: WorkshopDraft, min_steps: int = MIN_STEPS, max_steps: int = MAX_STEPS
) -> WorkshopDraft:
    """Trim/expand ``draft.hands_on_steps`` into the step band (AC7)."""
    steps = enforce_step_band(draft.hands_on_steps, min_steps, max_steps)
    if steps == draft.hands_on_steps:
        return draft
    return dataclasses.replace(draft, hands_on_steps=steps)


def _build_hands_on_steps(
    brief: ResearchBrief, context: dict[str, object]
) -> list[str]:
    cloud = context.get("cloud")
    cloud_note = f" on {str(cloud).upper()}" if cloud else ""
    return [
        f"Set up a local environment for: {brief.exercise_idea}.",
        f"Implement the core exercise{cloud_note}: {brief.exercise_idea}.",
        "Run your implementation and capture its output.",
        "Compare your output against the expected result and note any discrepancies.",
    ]


def _build_self_check_items() -> list[str]:
    return [
        "I completed every hands-on step without skipping any.",
        "I verified my output against the expected result.",
        "I can explain this topic's practical relevance in one sentence.",
    ]


def _build_initial_draft(
    brief: ResearchBrief, context: dict[str, object]
) -> WorkshopDraft:
    language = context["language"]
    cloud = context.get("cloud")
    cloud_note = f" using {str(cloud).upper()}" if cloud else ""
    basics_note = (
        " Senior-level basics for this stack are assumed and not re-explained here."
        if context.get("suppress_known_basics")
        else ""
    )
    quantum_note = str(context.get("quantum_note") or "")
    constraints = cast("tuple[str, ...]", context.get("constraints") or ())
    constraints_note = (
        f" Environment constraints: {', '.join(str(c) for c in constraints)}."
        if constraints
        else ""
    )
    overview_hook, why_rest = _split_rationale(brief.rationale)
    sections = {
        HEADING_OVERVIEW: f"{brief.title}. {overview_hook}",
        HEADING_WHY_IT_MATTERS_NOW: (
            f"{why_rest}\n\n"
            f"This is the moment to build hands-on fluency here — the "
            f"underlying technology is moving quickly, and today's "
            f"exercise gives you real, current practice instead of dated "
            f"theory."
        ),
        HEADING_CORE_CONCEPTS: _build_core_concepts(brief.key_facts),
        HEADING_PREREQUISITES: (
            f"A {language} environment is assumed{cloud_note}."
            f"{basics_note}{quantum_note}{constraints_note}"
        ),
        HEADING_VERIFICATION: (
            "Confirm your output matches the expected result described in "
            "the hands-on exercise above."
        ),
        HEADING_FURTHER_READING: (
            "\n".join(f"- {link}" for link in brief.source_links)
            if brief.source_links
            else "See the primary sources referenced in today's research brief."
        ),
    }
    return WorkshopDraft(
        title=brief.title,
        domain=brief.domain,
        slug=brief.slug,
        sections=sections,
        hands_on_steps=_build_hands_on_steps(brief, context),
        self_check_items=_build_self_check_items(),
    )


class Compiler:
    """Assembles a :class:`WorkshopDraft` from a :class:`ResearchBrief`."""

    def __init__(self, profile: PersonalizationProfile | None = None) -> None:
        # Left unset, reads inputs/profile.toml on construction; tests that
        # always pass an explicit profile never touch the filesystem here.
        self._profile = profile or load_personalization_profile()

    def run(self, brief: ResearchBrief) -> WorkshopDraft:
        context = build_render_context(brief, self._profile)
        draft = _build_initial_draft(brief, context)
        draft = finalize_word_count(draft)
        draft = finalize_step_count(draft)
        return draft
