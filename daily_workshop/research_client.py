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
ANTHROPIC_MODEL: str = "claude-sonnet-4-5"
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
            "max_tokens": 1024,
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
            f"matching these already-covered slugs: {exclusions}. Respond with "
            f"a JSON object: title, rationale, key_facts (3-5 items), "
            f"source_links, exercise_idea."
        )

    @staticmethod
    def _parse_response(domain: str, payload: dict) -> ResearchBrief | None:
        try:
            text = payload["content"][0]["text"]
            data = json.loads(text)
        except (KeyError, IndexError, ValueError) as exc:
            raise ResearchClientError(
                f"Anthropic research response for domain={domain} was not "
                f"parseable: {exc}"
            ) from exc
        title = data["title"]
        return ResearchBrief(
            domain=domain,
            title=title,
            slug=slugify(title),
            rationale=data["rationale"],
            key_facts=tuple(data.get("key_facts", [])),
            source_links=tuple(data.get("source_links", [])),
            exercise_idea=data["exercise_idea"],
        )
