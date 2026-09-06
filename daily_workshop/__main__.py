"""Thin CLI entrypoint: wires Researcher -> Compiler -> Teacher, nothing else.

Run with ``python -m daily_workshop`` (AC1). No task-scheduling or
background-daemon integration lives here or anywhere else in this package
by design (AC9) — Omar runs this manually each morning.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Protocol, TypeVar

from daily_workshop.compiler import Compiler
from daily_workshop.research_client import AnthropicResearchClient
from daily_workshop.researcher import Researcher
from daily_workshop.teacher import DEFAULT_WORKSHOPS_DIR, Teacher
from daily_workshop.topic_store import DEFAULT_TOPIC_STORE_PATH, TopicStore

REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DEFAULT_KEYS_PATH: Path = REPO_ROOT / "inputs" / "KEYS.md"

logger = logging.getLogger(__name__)

BriefT_co = TypeVar("BriefT_co", covariant=True)
DraftT_co = TypeVar("DraftT_co", covariant=True)
ResultT_co = TypeVar("ResultT_co", covariant=True)
BriefT_contra = TypeVar("BriefT_contra", contravariant=True)
DraftT_contra = TypeVar("DraftT_contra", contravariant=True)


class _ResearcherLike(Protocol[BriefT_co]):
    """Structural interface `run()` depends on — matches :class:`Researcher`
    and any test fake with a compatible `run()` shape (DI over concrete types,
    per backend.md's "Dependency injection over globals" rule)."""

    def run(self) -> BriefT_co:
        ...


class _CompilerLike(Protocol[BriefT_contra, DraftT_co]):
    def run(self, brief: BriefT_contra) -> DraftT_co:
        ...


class _TeacherLike(Protocol[DraftT_contra, ResultT_co]):
    def run(self, draft: DraftT_contra) -> ResultT_co:
        ...


# Plain (invariant) TypeVars for the `run()` signature below — these just bind
# the Brief/Draft/Result type consistently across the three collaborators;
# the variance annotations above only govern the Protocols' own subtyping.
BriefT = TypeVar("BriefT")
DraftT = TypeVar("DraftT")
ResultT = TypeVar("ResultT")


def run(
    researcher: _ResearcherLike[BriefT],
    compiler: _CompilerLike[BriefT, DraftT],
    teacher: _TeacherLike[DraftT, ResultT],
) -> int:
    """Run one full RESEARCHER -> COMPILER -> TEACHER pass.

    Returns 0 on success, 1 if any stage raises. This function takes its
    three collaborators as arguments (rather than constructing them itself)
    so it can be exercised in tests with fakes and zero real network/disk
    side effects.
    """
    try:
        brief = researcher.run()
        draft = compiler.run(brief)
        teacher.run(draft)
    except Exception:
        logger.exception("Daily Frontier Workshop run failed.")
        return 1
    return 0


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    topic_store = TopicStore(DEFAULT_TOPIC_STORE_PATH)
    researcher = Researcher(
        research_client=AnthropicResearchClient(keys_path=DEFAULT_KEYS_PATH),
        topic_store=topic_store,
    )
    compiler = Compiler()
    teacher = Teacher(topic_store=topic_store, workshops_dir=DEFAULT_WORKSHOPS_DIR)
    return run(researcher, compiler, teacher)


if __name__ == "__main__":
    sys.exit(main())
