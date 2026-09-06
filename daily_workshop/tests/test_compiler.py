# REQ-007: Time-budget enforcement. REQ-011: Personalization applied.
from __future__ import annotations

import pytest

from daily_workshop.compiler import (
    NARRATIVE_HEADINGS,
    Compiler,
    build_render_context,
    enforce_step_band,
    enforce_word_band,
    finalize_step_count,
    finalize_word_count,
    total_word_count,
)
from daily_workshop.constants import (
    HEADING_CORE_CONCEPTS,
    MAX_STEPS,
    MAX_WORDS,
    MIN_STEPS,
    MIN_WORDS,
)
from daily_workshop.models import PersonalizationProfile, ResearchBrief, WorkshopDraft


def _words(n: int, word: str = "word") -> str:
    return " ".join([word] * n)


def _brief(domain: str = "agentic_ai", **overrides: object) -> ResearchBrief:
    defaults: dict[str, object] = {
        "domain": domain,
        "title": "Topic X",
        "slug": "topic-x",
        "rationale": "Because it matters.",
        "key_facts": ("fact 1", "fact 2", "fact 3"),
        "source_links": ("https://example.com",),
        "exercise_idea": "Do the thing.",
    }
    defaults.update(overrides)
    return ResearchBrief(**defaults)  # type: ignore[arg-type]


def _profile(**overrides: object) -> PersonalizationProfile:
    defaults: dict[str, object] = {
        "preferred_language": "python",
        "preferred_cloud": "aws",
        "known_technologies": ("rest_apis", "docker", "kubernetes"),
        "linting_tools": ("flake8", "pylint", "mypy"),
        "formatter": "black",
        "quantum_background": False,
        "agentic_framework_familiarity": False,
    }
    defaults.update(overrides)
    return PersonalizationProfile(**defaults)  # type: ignore[arg-type]


def _draft_with_core_word_count(n: int) -> WorkshopDraft:
    sections = {heading: "" for heading in NARRATIVE_HEADINGS}
    sections[HEADING_CORE_CONCEPTS] = _words(n)
    return WorkshopDraft(
        title="T",
        domain="agentic_ai",
        slug="t",
        sections=sections,
        hands_on_steps=["step"] * MIN_STEPS,
        self_check_items=["check"],
    )


# ─── TC-007: word-count band (pure function) ────────────────────────────────


def test_enforce_word_band_leaves_in_band_prose_unchanged() -> None:
    # TC-007-01
    prose = _words(1100)
    assert enforce_word_band(prose) == prose


def test_enforce_word_band_expands_under_band_prose() -> None:
    # TC-007-02
    prose = _words(500)
    result = enforce_word_band(prose)
    assert MIN_WORDS <= len(result.split()) <= MAX_WORDS
    assert len(result.split()) == MIN_WORDS


def test_enforce_word_band_trims_over_band_prose() -> None:
    # TC-007-03
    prose = _words(2000)
    result = enforce_word_band(prose)
    assert MIN_WORDS <= len(result.split()) <= MAX_WORDS
    assert len(result.split()) == MAX_WORDS


# ─── TC-007: step-count band (pure function) ────────────────────────────────


def test_enforce_step_band_expands_3_steps_to_at_least_4() -> None:
    # TC-007-04
    steps = ["s1", "s2", "s3"]
    result = enforce_step_band(steps)
    assert len(result) >= MIN_STEPS
    assert result[:3] == steps


@pytest.mark.parametrize("count", [MIN_STEPS, MAX_STEPS])
def test_enforce_step_band_leaves_boundary_counts_unchanged(count: int) -> None:
    # TC-007-05
    steps = [f"s{i}" for i in range(count)]
    assert enforce_step_band(steps) == steps


def test_enforce_step_band_trims_9_steps_to_at_most_8() -> None:
    # TC-007-06
    steps = [f"s{i}" for i in range(9)]
    result = enforce_step_band(steps)
    assert len(result) <= MAX_STEPS


# ─── TC-007: draft-level finalize (what Compiler.run actually calls) ───────


def test_finalize_word_count_leaves_in_band_draft_unchanged() -> None:
    # TC-007-01
    draft = _draft_with_core_word_count(1100)
    result = finalize_word_count(draft)
    assert total_word_count(result) == 1100


def test_finalize_word_count_expands_under_band_draft_into_band() -> None:
    # TC-007-02
    draft = _draft_with_core_word_count(500)
    result = finalize_word_count(draft)
    assert MIN_WORDS <= total_word_count(result) <= MAX_WORDS


def test_finalize_word_count_trims_over_band_draft_into_band() -> None:
    # TC-007-03
    draft = _draft_with_core_word_count(2000)
    result = finalize_word_count(draft)
    assert MIN_WORDS <= total_word_count(result) <= MAX_WORDS


def test_finalize_step_count_expands_and_trims() -> None:
    short_draft = _draft_with_core_word_count(1000)
    short_draft.hands_on_steps = ["s1", "s2"]
    assert len(finalize_step_count(short_draft).hands_on_steps) >= MIN_STEPS

    long_draft = _draft_with_core_word_count(1000)
    long_draft.hands_on_steps = [f"s{i}" for i in range(9)]
    assert len(finalize_step_count(long_draft).hands_on_steps) <= MAX_STEPS


def test_compiler_module_imports_named_constants_not_magic_numbers() -> None:
    # TC-007-07
    import inspect

    import daily_workshop.compiler as compiler_module

    source = inspect.getsource(compiler_module)
    for literal in ("900", "1400"):
        assert literal not in source, f"found magic number {literal!r} in compiler.py"
    assert compiler_module.MIN_WORDS is MIN_WORDS
    assert compiler_module.MAX_WORDS is MAX_WORDS
    assert compiler_module.MIN_STEPS is MIN_STEPS
    assert compiler_module.MAX_STEPS is MAX_STEPS


# ─── TC-011: personalization ────────────────────────────────────────────────


def test_personalization_profile_fields_read_during_render_context_build() -> None:
    # TC-011-01
    brief = _brief(domain="agentic_ai")
    profile = _profile(preferred_language="python")

    context = build_render_context(brief, profile)

    assert context["language"] == "python"


def test_cloud_domain_brief_gets_cloud_from_profile() -> None:
    # TC-011-02
    brief = _brief(domain="cloud_computing")
    profile = _profile(preferred_cloud="aws")

    context = build_render_context(brief, profile)

    assert context["cloud"] == "aws"


def test_non_cloud_domain_brief_gets_no_cloud() -> None:
    brief = _brief(domain="quantum_computing")
    profile = _profile(preferred_cloud="aws")

    context = build_render_context(brief, profile)

    assert context["cloud"] is None


def test_senior_fluency_suppression_flag_exercised_for_docker_topic() -> None:
    # TC-011-03
    brief = _brief(
        domain="agentic_ai",
        title="Containerizing an Agent with Docker",
        rationale="Docker packaging for reproducible agent deployments.",
    )
    profile = _profile(known_technologies=("docker", "kubernetes", "rest_apis"))

    context = build_render_context(brief, profile)

    assert context["suppress_known_basics"] is True


def test_senior_fluency_suppression_flag_false_when_topic_is_unrelated() -> None:
    brief = _brief(
        domain="quantum_computing", title="Qiskit Circuits", rationale="Quantum gates."
    )
    profile = _profile(known_technologies=("docker", "kubernetes", "rest_apis"))

    context = build_render_context(brief, profile)

    assert context["suppress_known_basics"] is False


def test_compiler_run_produces_draft_within_word_and_step_bands() -> None:
    brief = _brief(domain="cloud_computing")
    compiler = Compiler(profile=_profile())

    draft = compiler.run(brief)

    assert MIN_WORDS <= total_word_count(draft) <= MAX_WORDS
    assert MIN_STEPS <= len(draft.hands_on_steps) <= MAX_STEPS
    assert draft.self_check_items
