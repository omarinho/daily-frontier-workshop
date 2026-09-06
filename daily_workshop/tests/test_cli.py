# REQ-001: Single CLI entrypoint runs the full pipeline.
from __future__ import annotations

from datetime import date
from pathlib import Path

from daily_workshop.__main__ import _parse_args, run, run_with_preview
from daily_workshop.constants import REQUIRED_HEADINGS
from daily_workshop.models import WorkshopDraft
from daily_workshop.teacher import Teacher
from daily_workshop.topic_store import TopicStore


class _CallOrderSpy:
    def __init__(self) -> None:
        self.calls: list[str] = []


class _FakeResearcher:
    def __init__(self, spy: _CallOrderSpy) -> None:
        self._spy = spy

    def run(self) -> str:
        self._spy.calls.append("researcher")
        return "brief"


class _FakeCompiler:
    def __init__(self, spy: _CallOrderSpy) -> None:
        self._spy = spy

    def run(self, brief: str) -> str:
        assert brief == "brief"
        self._spy.calls.append("compiler")
        return "draft"


class _FakeTeacher:
    def __init__(self, spy: _CallOrderSpy, raise_error: bool = False) -> None:
        self._spy = spy
        self._raise_error = raise_error

    def run(self, draft: str) -> str:
        assert draft == "draft"
        self._spy.calls.append("teacher")
        if self._raise_error:
            raise RuntimeError("teacher failed")
        return "path"


def test_entrypoint_with_fakes_runs_full_pipeline_and_exits_0() -> None:
    # TC-001-01
    spy = _CallOrderSpy()
    exit_code = run(_FakeResearcher(spy), _FakeCompiler(spy), _FakeTeacher(spy))

    assert exit_code == 0
    assert spy.calls == ["researcher", "compiler", "teacher"]


def test_call_order_spy_proves_stage_ordering() -> None:
    # TC-001-02
    spy = _CallOrderSpy()
    run(_FakeResearcher(spy), _FakeCompiler(spy), _FakeTeacher(spy))

    assert (
        spy.calls.index("researcher")
        < spy.calls.index("compiler")
        < spy.calls.index("teacher")
    )


def test_teacher_raising_makes_entrypoint_exit_non_zero() -> None:
    # TC-001-03 [inferred]
    spy = _CallOrderSpy()
    exit_code = run(
        _FakeResearcher(spy), _FakeCompiler(spy), _FakeTeacher(spy, raise_error=True)
    )

    assert exit_code != 0
    assert spy.calls == ["researcher", "compiler", "teacher"]


def test_researcher_raising_makes_entrypoint_exit_non_zero_without_calling_compiler() -> (
    None
):
    spy = _CallOrderSpy()

    class _RaisingResearcher:
        def run(self) -> str:
            raise RuntimeError("researcher failed")

    exit_code = run(_RaisingResearcher(), _FakeCompiler(spy), _FakeTeacher(spy))

    assert exit_code != 0
    assert spy.calls == []


# ─── --preview mode ─────────────────────────────────────────────────────────


def _preview_draft(**overrides: object) -> WorkshopDraft:
    sections = {
        heading: f"Body text for {heading}."
        for heading in REQUIRED_HEADINGS
        if heading not in ("Hands-On Exercise", "Self-Check Checklist")
    }
    defaults: dict[str, object] = {
        "title": "Preview Topic",
        "domain": "agentic_ai",
        "slug": "preview-topic",
        "sections": sections,
        "hands_on_steps": ["Step one.", "Step two.", "Step three.", "Step four."],
        "self_check_items": ["I did the thing."],
    }
    defaults.update(overrides)
    return WorkshopDraft(**defaults)  # type: ignore[arg-type]


class _FakeResearcherReturning:
    def __init__(self, value: object, raise_error: bool = False) -> None:
        self._value = value
        self._raise_error = raise_error

    def run(self) -> object:
        if self._raise_error:
            raise RuntimeError("researcher failed")
        return self._value


class _FakeCompilerReturning:
    def __init__(self, draft: WorkshopDraft) -> None:
        self._draft = draft

    def run(self, brief: object) -> WorkshopDraft:
        return self._draft


class _RecordingConfirm:
    def __init__(self, answer: bool) -> None:
        self.answer = answer
        self.called = False
        self.prompt: str | None = None

    def __call__(self, prompt: str) -> bool:
        self.called = True
        self.prompt = prompt
        return self.answer


def _teacher_and_store(tmp_path: Path) -> tuple[Teacher, TopicStore]:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    teacher = Teacher(
        topic_store=topic_store,
        workshops_dir=tmp_path / "workshops",
        today=date(2026, 3, 4),
    )
    return teacher, topic_store


def test_preview_confirmed_writes_file_and_records_history(tmp_path: Path) -> None:
    draft = _preview_draft()
    teacher, topic_store = _teacher_and_store(tmp_path)
    printed: list[str] = []
    confirm = _RecordingConfirm(answer=True)

    exit_code = run_with_preview(
        _FakeResearcherReturning("brief"),
        _FakeCompilerReturning(draft),
        teacher,
        confirm=confirm,
        print_fn=printed.append,
    )

    assert exit_code == 0
    assert confirm.called
    assert any("Preview Topic" in line for line in printed)
    written = list((tmp_path / "workshops").glob("*.md"))
    assert len(written) == 1
    assert len(topic_store.load_records()) == 1


def test_preview_declined_writes_nothing_and_leaves_history_untouched(
    tmp_path: Path,
) -> None:
    draft = _preview_draft()
    teacher, topic_store = _teacher_and_store(tmp_path)
    printed: list[str] = []
    confirm = _RecordingConfirm(answer=False)

    exit_code = run_with_preview(
        _FakeResearcherReturning("brief"),
        _FakeCompilerReturning(draft),
        teacher,
        confirm=confirm,
        print_fn=printed.append,
    )

    assert exit_code == 0
    assert not (tmp_path / "workshops").exists() or not list(
        (tmp_path / "workshops").glob("*.md")
    )
    assert topic_store.load_records() == []
    assert any("Discarded" in line for line in printed)


def test_preview_shows_rendered_markdown_before_prompting(tmp_path: Path) -> None:
    draft = _preview_draft(title="Something Distinctive")
    teacher, _ = _teacher_and_store(tmp_path)
    printed: list[str] = []
    confirm = _RecordingConfirm(answer=False)

    run_with_preview(
        _FakeResearcherReturning("brief"),
        _FakeCompilerReturning(draft),
        teacher,
        confirm=confirm,
        print_fn=printed.append,
    )

    assert any("Something Distinctive" in line for line in printed)
    assert confirm.called  # markdown was printed (above) before we ever confirmed


def test_preview_researcher_failure_exits_nonzero_without_prompting(
    tmp_path: Path,
) -> None:
    teacher, _ = _teacher_and_store(tmp_path)
    confirm = _RecordingConfirm(answer=True)

    exit_code = run_with_preview(
        _FakeResearcherReturning(None, raise_error=True),
        _FakeCompilerReturning(_preview_draft()),
        teacher,
        confirm=confirm,
        print_fn=lambda _: None,
    )

    assert exit_code != 0
    assert not confirm.called


# ─── CLI argument parsing ───────────────────────────────────────────────────


def test_parse_args_defaults_to_normal_run() -> None:
    args = _parse_args([])
    assert args.command is None
    assert args.preview is False


def test_parse_args_stats_command() -> None:
    args = _parse_args(["stats"])
    assert args.command == "stats"


def test_parse_args_preview_flag() -> None:
    args = _parse_args(["--preview"])
    assert args.preview is True
