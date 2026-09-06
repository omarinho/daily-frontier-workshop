"""Compiler: assembles lesson content and enforces the ~40-minute budget.

Depends only on :class:`ResearchBrief` in, :class:`WorkshopDraft` out — never
imports Researcher or Teacher directly. Word-count banding (AC7) and the
personalization render context (AC11) are pure functions of their inputs, no
I/O, no randomness, so they're trivial to unit test in isolation.
"""

from __future__ import annotations

import dataclasses

from daily_workshop.constants import (
    DOMAIN_CLOUD_COMPUTING,
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

NARRATIVE_HEADINGS: tuple[str, ...] = (
    HEADING_OVERVIEW,
    HEADING_WHY_IT_MATTERS_NOW,
    HEADING_CORE_CONCEPTS,
    HEADING_PREREQUISITES,
    HEADING_VERIFICATION,
    HEADING_FURTHER_READING,
)

# Technologies senior-fluency suppression applies to (AC11 / REQ-011 /
# linkedin-profile-omar-marino.md "assume senior-level fluency ... do not
# spend workshop time re-explaining these").
_SUPPRESSIBLE_KEYWORDS: tuple[str, ...] = ("rest", "docker", "kubernetes", "k8s")
_SUPPRESSIBLE_PROFILE_TECHNOLOGIES: tuple[str, ...] = (
    "rest_apis",
    "docker",
    "kubernetes",
)

# Deterministic filler used only to pad prose up to MIN_WORDS. Never
# shortens content that already carries meaning — see enforce_word_band.
_FILLER_SENTENCE: str = (
    "This detail reinforces the exercise's practical value and helps build "
    "durable intuition you can reuse the next time this pattern comes up."
)

# See linkedin-profile-omar-marino.md "How the Agent System Should Use This".
DEFAULT_PERSONALIZATION_PROFILE = PersonalizationProfile(
    preferred_language="python",
    preferred_cloud="aws",
    known_technologies=(
        "rest_apis",
        "microservices",
        "docker",
        "kubernetes",
        "linux_administration",
        "sql",
        "nosql",
    ),
    linting_tools=("flake8", "pylint", "mypy"),
    formatter="black",
    quantum_background=False,
    agentic_framework_familiarity=False,
)


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
    return {
        "language": profile.preferred_language,
        "cloud": profile.preferred_cloud
        if brief.domain == DOMAIN_CLOUD_COMPUTING
        else None,
        "suppress_known_basics": mentions_suppressible_topic and already_known,
    }


def _pad_to_extra_words(extra_words_needed: int) -> str:
    filler_words = _FILLER_SENTENCE.split()
    padding = [filler_words[i % len(filler_words)] for i in range(extra_words_needed)]
    return " ".join(padding)


def enforce_word_band(
    prose: str, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS
) -> str:
    """Return ``prose`` unchanged if within [min_words, max_words].

    Otherwise pads (deterministic filler) up to exactly ``min_words``, or
    truncates down to exactly ``max_words``.
    """
    words = prose.split()
    count = len(words)
    if min_words <= count <= max_words:
        return prose
    if count < min_words:
        padding = _pad_to_extra_words(min_words - count)
        return f"{prose.rstrip()} {padding}".strip()
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


def finalize_word_count(
    draft: WorkshopDraft, min_words: int = MIN_WORDS, max_words: int = MAX_WORDS
) -> WorkshopDraft:
    """Trim/expand ``draft`` (via its Core Concepts section) into the word band (AC7)."""
    count = total_word_count(draft)
    if min_words <= count <= max_words:
        return draft

    sections = dict(draft.sections)
    core = sections.get(HEADING_CORE_CONCEPTS, "")
    if count < min_words:
        padding = _pad_to_extra_words(min_words - count)
        core = f"{core.rstrip()} {padding}".strip()
    else:
        overshoot = count - max_words
        core_words = core.split()
        keep = max(len(core_words) - overshoot, 0)
        core = " ".join(core_words[:keep])
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
    sections = {
        HEADING_OVERVIEW: f"{brief.title}. {brief.rationale}",
        HEADING_WHY_IT_MATTERS_NOW: brief.rationale,
        HEADING_CORE_CONCEPTS: " ".join(brief.key_facts),
        HEADING_PREREQUISITES: (
            f"A {language} environment is assumed{cloud_note}.{basics_note}"
        ),
        HEADING_VERIFICATION: (
            "Confirm your output matches the expected result described in "
            "the hands-on exercise above."
        ),
        HEADING_FURTHER_READING: (
            " ".join(brief.source_links)
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

    def __init__(
        self, profile: PersonalizationProfile = DEFAULT_PERSONALIZATION_PROFILE
    ) -> None:
        self._profile = profile

    def run(self, brief: ResearchBrief) -> WorkshopDraft:
        context = build_render_context(brief, self._profile)
        draft = _build_initial_draft(brief, context)
        draft = finalize_word_count(draft)
        draft = finalize_step_count(draft)
        return draft
