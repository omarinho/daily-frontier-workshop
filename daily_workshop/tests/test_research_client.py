# REQ-010: Secrets discipline for the research API key (AC10).
from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import daily_workshop
from daily_workshop.research_client import (
    ANTHROPIC_API_KEY_NAME,
    ANTHROPIC_MODEL,
    AnthropicResearchClient,
    ResearchClientError,
    read_key_from_keys_md,
)


def _models_response(*model_ids_with_dates: tuple[str, str]) -> MagicMock:
    """Build a mock urlopen() context manager returning a Models API payload."""
    payload = {
        "data": [
            {"id": model_id, "created_at": created_at}
            for model_id, created_at in model_ids_with_dates
        ]
    }
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    return response

_VALID_BRIEF_JSON = (
    '{"title": "MCP Servers", "rationale": "Growing adoption", '
    '"key_facts": ["a", "b", "c"], '
    '"source_links": ["https://modelcontextprotocol.io"], '
    '"exercise_idea": "Build a minimal MCP server"}'
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


def test_parse_response_skips_leading_web_search_blocks() -> None:
    # Regression: a real web-search-enabled response puts server_tool_use /
    # web_search_tool_result blocks BEFORE the final text block — the parser
    # must not assume content[0] is text.
    payload = {
        "content": [
            {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"},
            {"type": "web_search_tool_result", "tool_use_id": "srvtoolu_1"},
            {"type": "text", "text": _VALID_BRIEF_JSON},
        ]
    }

    brief = AnthropicResearchClient._parse_response("agentic_ai", payload)

    assert brief is not None
    assert brief.title == "MCP Servers"
    assert brief.slug == "mcp-servers"
    assert brief.source_links == ("https://modelcontextprotocol.io",)


def test_parse_response_strips_surrounding_prose_and_code_fences() -> None:
    payload = {
        "content": [
            {"type": "text", "text": f"```json\n{_VALID_BRIEF_JSON}\n```"},
        ]
    }

    brief = AnthropicResearchClient._parse_response("agentic_ai", payload)

    assert brief is not None
    assert brief.title == "MCP Servers"


def test_parse_response_flattens_key_facts_and_source_links_returned_as_objects() -> (
    None
):
    # Regression: the model sometimes nests list entries as objects
    # (e.g. {"fact": "...", "explanation": "..."}) despite the prompt
    # asking for plain strings — this must not crash the run.
    brief_json = (
        '{"title": "MCP Servers", "rationale": "Growing adoption", '
        '"key_facts": [{"fact": "Point one", "explanation": "because X"}, '
        '"Plain fact two"], '
        '"source_links": [{"url": "https://example.com", "title": "Docs"}], '
        '"exercise_idea": "Build a minimal MCP server"}'
    )
    payload = {"content": [{"type": "text", "text": brief_json}]}

    brief = AnthropicResearchClient._parse_response("agentic_ai", payload)

    assert brief is not None
    assert brief.key_facts[0] == "Point one because X"
    assert brief.key_facts[1] == "Plain fact two"
    assert brief.source_links[0] == "https://example.com Docs"


def test_parse_response_raises_clear_error_when_no_text_block_present() -> None:
    payload = {
        "content": [
            {"type": "server_tool_use", "id": "srvtoolu_1", "name": "web_search"},
        ],
        "stop_reason": "max_tokens",
    }

    with pytest.raises(ResearchClientError, match="no text block"):
        AnthropicResearchClient._parse_response("agentic_ai", payload)


def test_current_model_picks_newest_sonnet_tier_model(tmp_path: Path) -> None:
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")
    client = AnthropicResearchClient(keys_path=keys_path)
    response = _models_response(
        ("claude-opus-5", "2026-07-24T00:00:00Z"),
        ("claude-sonnet-5", "2026-01-01T00:00:00Z"),
        ("claude-sonnet-6", "2026-08-01T00:00:00Z"),
        ("claude-haiku-4-5-20251001", "2025-10-01T00:00:00Z"),
    )

    with patch("urllib.request.urlopen", return_value=response):
        model = client._current_model()

    assert model == "claude-sonnet-6"


def test_current_model_falls_back_when_no_sonnet_tier_model_listed(
    tmp_path: Path,
) -> None:
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")
    client = AnthropicResearchClient(keys_path=keys_path)
    response = _models_response(("claude-opus-5", "2026-07-24T00:00:00Z"))

    with patch("urllib.request.urlopen", return_value=response):
        model = client._current_model()

    assert model == ANTHROPIC_MODEL


def test_current_model_falls_back_on_network_error(tmp_path: Path) -> None:
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")
    client = AnthropicResearchClient(keys_path=keys_path)

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("no network"),
    ):
        model = client._current_model()

    assert model == ANTHROPIC_MODEL


def test_current_model_resolved_once_and_cached_per_instance(tmp_path: Path) -> None:
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")
    client = AnthropicResearchClient(keys_path=keys_path)
    response = _models_response(("claude-sonnet-5", "2026-01-01T00:00:00Z"))

    with patch("urllib.request.urlopen", return_value=response) as mock_urlopen:
        client._current_model()
        client._current_model()

    assert mock_urlopen.call_count == 1


def test_explicit_model_override_skips_the_network_lookup_entirely(
    tmp_path: Path,
) -> None:
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")
    client = AnthropicResearchClient(keys_path=keys_path, model="claude-sonnet-5")

    with patch("urllib.request.urlopen") as mock_urlopen:
        model = client._current_model()

    mock_urlopen.assert_not_called()
    assert model == "claude-sonnet-5"


def test_constructing_client_never_touches_the_network(tmp_path: Path) -> None:
    # __init__ must not call the Models API — resolution is lazy, on the
    # first fetch_brief()/_current_model() call, so simply instantiating a
    # client (as every other test in this file does) never hits network.
    keys_path = _write_keys_md(tmp_path, f"{ANTHROPIC_API_KEY_NAME}=sk-test\n")

    with patch("urllib.request.urlopen") as mock_urlopen:
        AnthropicResearchClient(keys_path=keys_path)

    mock_urlopen.assert_not_called()


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
