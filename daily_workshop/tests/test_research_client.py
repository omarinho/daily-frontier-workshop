# REQ-010: Secrets discipline for the research API key (AC10).
from __future__ import annotations

from pathlib import Path

import pytest

import daily_workshop
from daily_workshop.research_client import (
    ANTHROPIC_API_KEY_NAME,
    AnthropicResearchClient,
    ResearchClientError,
    read_key_from_keys_md,
)

_DAILY_WORKSHOP_DIR = Path(daily_workshop.__file__).resolve().parent


def _write_keys_md(tmp_path: Path, contents: str) -> Path:
    keys_path = tmp_path / "KEYS.md"
    keys_path.write_text(contents, encoding="utf-8")
    return keys_path


def test_concrete_client_reads_key_only_via_keys_md_parser(tmp_path: Path) -> None:
    # TC-010-01
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test-value\n")

    client = AnthropicResearchClient(keys_path=keys_path)

    assert client._api_key == "sk-test-value"


def test_read_key_from_keys_md_ignores_comments_and_other_keys(tmp_path: Path) -> None:
    keys_path = _write_keys_md(
        tmp_path,
        "\n".join(
            [
                "# API Keys",
                "FIGMA_API_TOKEN=unrelated",
                f"{ANTHROPIC_API_KEY_NAME}=sk-real-value",
                "OTHER=x",
            ]
        ),
    )

    assert read_key_from_keys_md(ANTHROPIC_API_KEY_NAME, keys_path) == "sk-real-value"


def test_missing_key_file_raises_clear_configuration_error(tmp_path: Path) -> None:
    # TC-010-03
    missing_path = tmp_path / "does-not-exist.md"

    with pytest.raises(ResearchClientError):
        AnthropicResearchClient(keys_path=missing_path)


def test_empty_key_value_raises_clear_configuration_error(tmp_path: Path) -> None:
    # TC-010-03
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=\n")

    with pytest.raises(ResearchClientError):
        AnthropicResearchClient(keys_path=keys_path)


def test_missing_key_entirely_raises_clear_configuration_error(tmp_path: Path) -> None:
    # TC-010-03
    keys_path = _write_keys_md(tmp_path, "FIGMA_API_TOKEN=abc\n")

    with pytest.raises(ResearchClientError):
        AnthropicResearchClient(keys_path=keys_path)


def test_no_dotenv_usage_anywhere_in_daily_workshop() -> None:
    # TC-010-02
    # Scoped to production source only — this test file necessarily mentions
    # the very substrings ("dotenv", ".env") it checks for, which would
    # otherwise flag itself as an offender.
    offending_files = []
    for py_file in _DAILY_WORKSHOP_DIR.rglob("*.py"):
        if "tests" in py_file.relative_to(_DAILY_WORKSHOP_DIR).parts:
            continue
        text = py_file.read_text(encoding="utf-8").lower()
        if ".env" in text or "dotenv" in text:
            offending_files.append(py_file)
    assert offending_files == []
