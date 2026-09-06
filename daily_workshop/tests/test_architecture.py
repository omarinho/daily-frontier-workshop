# REQ-009: No scheduler/daemon integration (deliberate constraint, AC9).
from __future__ import annotations

from pathlib import Path

import daily_workshop

_PACKAGE_DIR = Path(daily_workshop.__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parent

_SCHEDULER_MARKERS = (
    "import schedule",
    "from schedule",
    "apscheduler",
    "celery.beat",
    "cron",
    "systemd",
)


def _all_python_files() -> list[Path]:
    # Scoped to production source only — this test file (and its siblings)
    # necessarily *mentions* scheduler-related words while documenting what
    # they check for, which would otherwise flag itself as an offender.
    return [
        p
        for p in _PACKAGE_DIR.rglob("*.py")
        if "tests" not in p.relative_to(_PACKAGE_DIR).parts
    ]


def test_no_scheduler_package_imports_anywhere_in_daily_workshop() -> None:
    # TC-009-01
    offenders: list[str] = []
    for py_file in _all_python_files():
        text = py_file.read_text(encoding="utf-8").lower()
        for marker in _SCHEDULER_MARKERS:
            if marker in text:
                offenders.append(f"{py_file}: {marker!r}")
    assert offenders == [], offenders


def test_no_cron_or_service_config_files_in_daily_workshop() -> None:
    # TC-009-02
    scheduler_suffixes = (".timer", ".service")
    offenders = [
        str(p)
        for p in _PACKAGE_DIR.rglob("*")
        if p.is_file() and (p.suffix in scheduler_suffixes or p.name == "crontab")
    ]
    assert offenders == []


def test_main_module_has_no_polling_loop_or_daemon_construct() -> None:
    # TC-009-03 [inferred]
    main_source = (_PACKAGE_DIR / "__main__.py").read_text(encoding="utf-8")
    assert "while True" not in main_source
    assert "time.sleep" not in main_source


def test_no_scheduling_third_party_dependency_declared() -> None:
    """Belt-and-suspenders: no pyproject/requirements file in this package
    declares a scheduler dependency either."""
    dependency_files = list(_PACKAGE_DIR.rglob("requirements*.txt")) + list(
        _PACKAGE_DIR.rglob("pyproject.toml")
    )
    for dep_file in dependency_files:
        text = dep_file.read_text(encoding="utf-8").lower()
        for marker in ("schedule", "apscheduler", "celery"):
            assert marker not in text
