"""Teacher: validates structure, renders Markdown, writes the file, records history.

Depends only on :class:`WorkshopDraft` in — never imports Researcher or
Compiler directly. Owns the fixed section order (AC6) and the
deterministic, non-clobbering output path (AC2).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from daily_workshop.constants import (
    HEADING_HANDS_ON_EXERCISE,
    HEADING_SELF_CHECK,
    REQUIRED_HEADINGS,
)
from daily_workshop.models import TopicRecord, WorkshopDraft
from daily_workshop.topic_store import TopicStore

logger = logging.getLogger(__name__)

NARRATIVE_HEADINGS: tuple[str, ...] = tuple(
    heading
    for heading in REQUIRED_HEADINGS
    if heading not in (HEADING_HANDS_ON_EXERCISE, HEADING_SELF_CHECK)
)

DEFAULT_WORKSHOPS_DIR: Path = Path(__file__).resolve().parent.parent / "workshops"


class TeacherValidationError(Exception):
    """Raised when a WorkshopDraft is missing required structure before write."""


class Teacher:
    """Formats the final lesson and writes it to ``workshops/``."""

    def __init__(
        self,
        topic_store: TopicStore,
        workshops_dir: Path = DEFAULT_WORKSHOPS_DIR,
        today: date | None = None,
    ) -> None:
        self._workshops_dir = workshops_dir
        self._topic_store = topic_store
        self._today = today or datetime.now(timezone.utc).astimezone().date()

    def run(self, draft: WorkshopDraft) -> Path:
        """Validate, write, and record ``draft``. See :meth:`commit`."""
        return self.commit(draft)

    def commit(self, draft: WorkshopDraft) -> Path:
        """Write ``draft`` to disk and append its history record.

        Split out from :meth:`run` (which just calls this) so preview mode
        (``--preview``, see ``__main__.py``) can render and show a draft
        without committing it — nothing is written and no 90-day-dedup
        history entry is created unless this runs.
        """
        self._validate(draft)
        output_path = self._output_path_for(draft.slug)

        if output_path.exists():
            logger.info(
                "Workshop for slug=%s already exists today at %s; skipping "
                "write to avoid clobbering it.",
                draft.slug,
                output_path,
            )
            return output_path

        markdown = self.render_markdown(draft)
        self._workshops_dir.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")
        self._topic_store.append(
            TopicRecord(
                date=self._today,
                domain=draft.domain,
                slug=draft.slug,
                summary=self._one_line_summary(draft),
                word_count=self._word_count(draft),
            )
        )
        return output_path

    @staticmethod
    def _word_count(draft: WorkshopDraft) -> int:
        """Prose word count across narrative sections (mirrors compiler.py's
        ``total_word_count`` — duplicated rather than imported, since Teacher
        must never import Compiler, per this module's own architecture rule).
        """
        return sum(len(text.split()) for text in draft.sections.values())

    def _output_path_for(self, slug: str) -> Path:
        return self._workshops_dir / f"{self._today.isoformat()}-{slug}.md"

    @staticmethod
    def _validate(draft: WorkshopDraft) -> None:
        missing_sections = [
            heading for heading in NARRATIVE_HEADINGS if not draft.sections.get(heading)
        ]
        if missing_sections:
            raise TeacherValidationError(
                f"WorkshopDraft is missing required section(s): {missing_sections}"
            )
        if not draft.hands_on_steps:
            raise TeacherValidationError("WorkshopDraft has no hands-on steps.")
        if not draft.self_check_items:
            raise TeacherValidationError("WorkshopDraft has no self-check items.")

    @staticmethod
    def _one_line_summary(draft: WorkshopDraft) -> str:
        overview = draft.sections.get(REQUIRED_HEADINGS[0], draft.title)
        first_sentence = overview.split(". ")[0].strip()
        return first_sentence or draft.title

    @staticmethod
    def render_markdown(draft: WorkshopDraft) -> str:
        """Render ``draft`` as Markdown with headings in ``REQUIRED_HEADINGS`` order."""
        lines: list[str] = [f"# {draft.title}", ""]
        for heading in REQUIRED_HEADINGS:
            lines.append(f"## {heading}")
            lines.append("")
            if heading == HEADING_HANDS_ON_EXERCISE:
                for index, step in enumerate(draft.hands_on_steps, start=1):
                    lines.append(f"{index}. {step}")
            elif heading == HEADING_SELF_CHECK:
                for item in draft.self_check_items:
                    lines.append(f"- [ ] {item}")
            else:
                lines.append(draft.sections[heading])
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"
