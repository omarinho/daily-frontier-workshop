"""Injectable research-client interface plus the one concrete implementation.

Design choice (BuilderAgent, per ``plan.json.builder_notes.research_client_choice``):
the concrete client calls the Anthropic Messages API with the web-search tool
enabled, since Omar already standardizes on Claude/Anthropic tooling
elsewhere in this repo. Its API key is named ``ANTHROPIC_API_KEY`` and is
read exclusively from ``inputs/KEYS.md`` (see that file's "Adding more keys"
section) — never hardcoded, never loaded from a separate secrets config
file (AC10).

No test in this codebase ever calls :meth:`AnthropicResearchClient.fetch_brief`
against the real network — tests exercise only the constructor (key-reading
behavior) and use :class:`ResearchClient` fakes for everything else.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from daily_workshop.models import ResearchBrief
from daily_workshop.text_utils import slugify

ANTHROPIC_API_KEY_NAME: str = "ANTHROPIC_API_KEY"
ANTHROPIC_API_URL: str = "https://api.anthropic.com/v1/messages"
ANTHROPIC_API_VERSION: str = "2023-06-01"
ANTHROPIC_MODEL: str = "claude-sonnet-5"
ANTHROPIC_MAX_TOKENS: int = 4096
ANTHROPIC_REQUEST_TIMEOUT_SECONDS: int = 30


class ResearchClientError(Exception):
    """Raised when a ResearchClient cannot produce a research brief.

    The Researcher catches this and falls back to the seed-topic backlog
    (AC5) — it must never be swallowed silently.
    """


class ResearchClient(ABC):
    """Injectable interface. Production code depends only on this type."""

    @abstractmethod
    def fetch_brief(
        self, domain: str, excluded_slugs: frozenset[str]
    ) -> ResearchBrief | None:
        """Return one hands-on-capable topic for ``domain``.

        Implementations may return ``None`` or raise :class:`ResearchClientError`
        when research is unavailable; both are treated as a fallback trigger
        by the Researcher.
        """
        raise NotImplementedError


def read_key_from_keys_md(key_name: str, keys_path: Path) -> str:
    """Parse ``KEY=VALUE`` lines out of a KEYS.md-style file.

    Raises :class:`ResearchClientError` with a clear, actionable message if
    the file is missing or the key is absent/empty — never returns an empty
    string silently (REQ-010 / AC10).
    """
    if not keys_path.exists():
        raise ResearchClientError(
            f"{keys_path} not found; cannot read {key_name}. "
            f"Add `{key_name}=<value>` under KEYS.md's 'Adding more keys' section."
        )
    for line in keys_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        candidate_key, _, value = stripped.partition("=")
        if candidate_key.strip() == key_name:
            value = value.strip()
            if value:
                return value
            break
    raise ResearchClientError(
        f"{key_name} is missing or empty in {keys_path}. "
        f"Add `{key_name}=<value>` under KEYS.md's 'Adding more keys' section."
    )


class AnthropicResearchClient(ResearchClient):
    """Calls the Anthropic Messages API (with web search) for one topic."""

    def __init__(self, keys_path: Path, api_key: str | None = None) -> None:
        self._api_key = api_key or read_key_from_keys_md(
            ANTHROPIC_API_KEY_NAME, keys_path
        )

    def fetch_brief(
        self, domain: str, excluded_slugs: frozenset[str]
    ) -> ResearchBrief | None:
        request_body = {
            "model": ANTHROPIC_MODEL,
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(domain, excluded_slugs),
                }
            ],
        }
        request = urllib.request.Request(
            ANTHROPIC_API_URL,
            data=json.dumps(request_body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=ANTHROPIC_REQUEST_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise ResearchClientError(
                f"Anthropic research call failed for domain={domain}: {exc}"
            ) from exc
        return self._parse_response(domain, payload)

    @staticmethod
    def _build_prompt(domain: str, excluded_slugs: frozenset[str]) -> str:
        exclusions = ", ".join(sorted(excluded_slugs)) or "none"
        return (
            f"Find one current, practical, hands-on topic in the domain "
            f"'{domain}' for a senior Python/AWS engineer. Exclude topics "
            f"matching these already-covered slugs: {exclusions}. Use web "
            f"search to ground the topic in something current. "
            f"After searching, respond with ONLY a single JSON object as "
            f"your final message — no prose before or after it, no markdown "
            f"code fences — with these keys:\n"
            f"- title: short topic title.\n"
            f"- rationale: 2-3 full sentences on why this matters right now "
            f"(not a single fragment).\n"
            f"- key_facts: exactly 5 items, each a self-contained 1-2 sentence "
            f"explanation (not a short phrase) of a concrete, specific fact "
            f"you found via search — assume the reader is a senior engineer, "
            f"so explain the mechanism or implication, not just the label.\n"
            f"- source_links: list of URLs actually found via search.\n"
            f"- exercise_idea: 2-3 sentences describing a concrete hands-on "
            f"exercise, specific enough that someone could follow it as a "
            f"numbered checklist.\n"
            f"key_facts and source_links must each be a flat JSON array of "
            f"plain strings — not objects."
        )

    @staticmethod
    def _parse_response(domain: str, payload: dict) -> ResearchBrief | None:
        content_blocks = [
            block for block in payload.get("content", []) if isinstance(block, dict)
        ]
        text = "".join(
            block["text"] for block in content_blocks if block.get("type") == "text"
        )
        if not text:
            raise ResearchClientError(
                f"Anthropic research response for domain={domain} contained "
                f"no text block to parse (stop_reason="
                f"{payload.get('stop_reason')!r}, block types="
                f"{[b.get('type') for b in content_blocks]!r})."
            )
        data = AnthropicResearchClient._extract_json_object(domain, text)
        try:
            title = data["title"]
            rationale = data["rationale"]
            exercise_idea = data["exercise_idea"]
        except KeyError as exc:
            raise ResearchClientError(
                f"Anthropic research response for domain={domain} JSON was "
                f"missing required field: {exc}"
            ) from exc
        return ResearchBrief(
            domain=domain,
            title=title,
            slug=slugify(title),
            rationale=rationale,
            key_facts=tuple(
                AnthropicResearchClient._coerce_to_str(item)
                for item in data.get("key_facts", [])
            ),
            source_links=tuple(
                AnthropicResearchClient._coerce_to_str(item)
                for item in data.get("source_links", [])
            ),
            exercise_idea=exercise_idea,
        )

    @staticmethod
    def _coerce_to_str(item: object) -> str:
        """Flatten a list entry the model returned as an object, not a string.

        The prompt asks for plain strings, but the model sometimes still
        nests each entry as e.g. {"fact": "...", "explanation": "..."} or
        {"url": "...", "title": "..."} — join such objects' values rather
        than letting a shape mismatch crash the whole run.
        """
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            return " ".join(str(v) for v in item.values() if v)
        return str(item)

    @staticmethod
    def _extract_json_object(domain: str, text: str) -> dict:
        try:
            return json.loads(text)
        except ValueError:
            pass
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ResearchClientError(
                f"Anthropic research response for domain={domain} text "
                f"contained no JSON object to parse: {text[:200]!r}"
            )
        try:
            return json.loads(text[start : end + 1])
        except ValueError as exc:
            raise ResearchClientError(
                f"Anthropic research response for domain={domain} was not "
                f"parseable: {exc}"
            ) from exc
