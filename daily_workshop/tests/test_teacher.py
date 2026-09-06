# REQ-002: Deterministic output location, no silent clobber.
# REQ-006: Fixed Markdown section order.
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from daily_workshop.constants import HEADING_CORE_CONCEPTS, REQUIRED_HEADINGS
from daily_workshop.models import WorkshopDraft
from daily_workshop.teacher import Teacher, TeacherValidationError
from daily_workshop.topic_store import TopicStore

_HEADING_LINE = re.compile(r"^## (.+)$", re.MULTILINE)


def _draft(**overrides: object) -> WorkshopDraft:
    sections = {
        heading: f"Body text for {heading}."
        for heading in REQUIRED_HEADINGS
        if heading not in ("Hands-On Exercise", "Self-Check Checklist")
    }
    defaults: dict[str, object] = {
        "title": "Some Practical Topic",
        "domain": "agentic_ai",
        "slug": "some-practical-topic",
        "sections": sections,
        "hands_on_steps": ["Step one.", "Step two.", "Step three.", "Step four."],
        "self_check_items": ["I did the thing."],
    }
    defaults.update(overrides)
    return WorkshopDraft(**defaults)  # type: ignore[arg-type]


def _extract_headings(markdown: str) -> list[str]:
    return _HEADING_LINE.findall(markdown)


# ─── TC-006: fixed section order ────────────────────────────────────────────


def test_rendered_markdown_headings_exactly_match_required_order() -> None:
    # TC-006-01
    markdown = Teacher.render_markdown(_draft())
    assert _extract_headings(markdown) == list(REQUIRED_HEADINGS)


def test_validate_fails_when_a_required_section_is_missing(tmp_path: Path) -> None:
    # TC-006-02
    draft = _draft()
    del draft.sections[HEADING_CORE_CONCEPTS]
    teacher = Teacher(
        topic_store=TopicStore(tmp_path / "covered_topics.json"), workshops_dir=tmp_path
    )

    with pytest.raises(TeacherValidationError):
        teacher.run(draft)


def test_validate_fails_when_no_hands_on_steps(tmp_path: Path) -> None:
    draft = _draft(hands_on_steps=[])
    teacher = Teacher(
        topic_store=TopicStore(tmp_path / "covered_topics.json"), workshops_dir=tmp_path
    )

    with pytest.raises(TeacherValidationError):
        teacher.run(draft)


def test_validate_fails_when_no_self_check_items(tmp_path: Path) -> None:
    draft = _draft(self_check_items=[])
    teacher = Teacher(
        topic_store=TopicStore(tmp_path / "covered_topics.json"), workshops_dir=tmp_path
    )

    with pytest.raises(TeacherValidationError):
        teacher.run(draft)


# ─── TC-002: deterministic, non-clobbering output location ─────────────────


def test_run_writes_exactly_one_new_file_at_expected_path(tmp_path: Path) -> None:
    # TC-002-01
    workshops_dir = tmp_path / "workshops"
    teacher = Teacher(
        topic_store=TopicStore(tmp_path / "covered_topics.json"),
        workshops_dir=workshops_dir,
        today=date(2026, 3, 4),
    )

    output_path = teacher.run(_draft(slug="some-practical-topic"))

    assert output_path == workshops_dir / "2026-03-04-some-practical-topic.md"
    assert output_path.exists()
    written_files = list(workshops_dir.glob("*.md"))
    assert len(written_files) == 1


def test_second_same_day_run_does_not_clobber_first_file(tmp_path: Path) -> None:
    # TC-002-02
    workshops_dir = tmp_path / "workshops"
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    teacher = Teacher(
        topic_store=topic_store, workshops_dir=workshops_dir, today=date(2026, 3, 4)
    )

    first_path = teacher.run(_draft())
    first_bytes = first_path.read_bytes()

    second_path = teacher.run(_draft())

    assert second_path == first_path
    assert first_path.read_bytes() == first_bytes
    assert len(list(workshops_dir.glob("*.md"))) == 1
    # The skipped second run must not double-append to the topic store.
    assert len(topic_store.load_records()) == 1


def test_slug_determines_filename_deterministically(tmp_path: Path) -> None:
    # TC-002-03
    workshops_dir = tmp_path / "workshops"
    teacher = Teacher(
        topic_store=TopicStore(tmp_path / "covered_topics.json"),
        workshops_dir=workshops_dir,
        today=date(2026, 3, 4),
    )

    output_path = teacher.run(_draft(slug="mcp-model-context-protocol-servers"))

    assert output_path.name == "2026-03-04-mcp-model-context-protocol-servers.md"


def test_run_appends_one_topic_record(tmp_path: Path) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    teacher = Teacher(
        topic_store=topic_store,
        workshops_dir=tmp_path / "workshops",
        today=date(2026, 3, 4),
    )

    teacher.run(_draft(domain="cloud_computing", slug="a-topic"))

    records = topic_store.load_records()
    assert len(records) == 1
    assert records[0].domain == "cloud_computing"
    assert records[0].slug == "a-topic"
    assert records[0].date == date(2026, 3, 4)
