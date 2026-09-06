# REQ-001: Single CLI entrypoint runs the full pipeline.
from __future__ import annotations

from daily_workshop.__main__ import run


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
