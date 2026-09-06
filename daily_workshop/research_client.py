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
import logging
import re
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from pathlib import Path

from daily_workshop.models import ResearchBrief
from daily_workshop.text_utils import slugify

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY_NAME: str = "ANTHROPIC_API_KEY"
ANTHROPIC_API_URL: str = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MODELS_URL: str = "https://api.anthropic.com/v1/models"
ANTHROPIC_API_VERSION: str = "2023-06-01"
# Fallback only — used if the live model-list lookup fails or returns no
# Sonnet-tier match. AnthropicResearchClient queries ANTHROPIC_MODELS_URL on
# each run and picks the newest model matching MODEL_TIER_PATTERN, so a new
# Sonnet release is picked up automatically without editing this constant.
ANTHROPIC_MODEL: str = "claude-sonnet-5"
MODEL_TIER_PATTERN: re.Pattern[str] = re.compile(r"^claude-sonnet-\d")
ANTHROPIC_MAX_TOKENS: int = 4096
ANTHROPIC_REQUEST_TIMEOUT_SECONDS: int = 60


class ResearchClientError(Exception):
    """Raised when a ResearchClient cannot produce a research brief.

    The Researcher catches this and falls back to the seed-topic backlog
    (AC5) — it must never be swallowed silently.
    """


class ResearchClient(ABC):
    """Injectable interface. Production code depends only on this type."""

    @abstractmethod
    def fetch_brief(
        self,
        domain: str,
        excluded_slugs: frozenset[str],
        recent_titles: tuple[str, ...] = (),
    ) -> ResearchBrief | None:
        """Return one hands-on-capable topic for ``domain``.

        ``recent_titles`` (most recent first) are titles already covered in
        this domain, for topical-diversity guidance — distinct from
        ``excluded_slugs``, which is the hard 90-day dedup exclusion.
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

    def __init__(
        self,
        keys_path: Path,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key or read_key_from_keys_md(
            ANTHROPIC_API_KEY_NAME, keys_path
        )
        # `model` pins an exact model, skipping the live lookup entirely —
        # used by tests and available as a manual override. Left unset, the
        # model is resolved once per instance, lazily, on the first
        # fetch_brief() call (never in __init__, so constructing a client
        # never touches the network on its own).
        self._model_override = model
        self._resolved_model: str | None = None

    def _current_model(self) -> str:
        if self._model_override:
            return self._model_override
        if self._resolved_model is None:
            self._resolved_model = self._resolve_current_model()
        return self._resolved_model

    def _resolve_current_model(self) -> str:
        """Query the Models API and return the newest Sonnet-tier model id.

        Falls back to ANTHROPIC_MODEL (the last known-good pinned snapshot)
        on any network failure or if no Sonnet-tier model is listed, so a
        model-list outage or API change never blocks a run.
        """
        request = urllib.request.Request(
            ANTHROPIC_MODELS_URL,
            headers={
                "x-api-key": self._api_key,
                "anthropic-version": ANTHROPIC_API_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(
                request, timeout=ANTHROPIC_REQUEST_TIMEOUT_SECONDS
            ) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning(
                "Could not list Anthropic models (%s); falling back to "
                "pinned model %r.",
                exc,
                ANTHROPIC_MODEL,
            )
            return ANTHROPIC_MODEL
        candidates = [
            entry
            for entry in payload.get("data", [])
            if isinstance(entry, dict) and MODEL_TIER_PATTERN.match(entry.get("id", ""))
        ]
        if not candidates:
            logger.warning(
                "No Sonnet-tier model found in the Anthropic model list; "
                "falling back to pinned model %r.",
                ANTHROPIC_MODEL,
            )
            return ANTHROPIC_MODEL
        newest = max(candidates, key=lambda entry: entry.get("created_at", ""))
        model_id = str(newest["id"])
        if model_id != ANTHROPIC_MODEL:
            logger.info(
                "Using %r (newer than the pinned fallback %r).",
                model_id,
                ANTHROPIC_MODEL,
            )
        return model_id

    def fetch_brief(
        self,
        domain: str,
        excluded_slugs: frozenset[str],
        recent_titles: tuple[str, ...] = (),
    ) -> ResearchBrief | None:
        request_body = {
            "model": self._current_model(),
            "max_tokens": ANTHROPIC_MAX_TOKENS,
            "tools": [{"type": "web_search_20250305", "name": "web_search"}],
            "messages": [
                {
                    "role": "user",
                    "content": self._build_prompt(domain, excluded_slugs, recent_titles),
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
    def _build_prompt(
        domain: str,
        excluded_slugs: frozenset[str],
        recent_titles: tuple[str, ...] = (),
    ) -> str:
        exclusions = ", ".join(sorted(excluded_slugs)) or "none"
        diversity_note = ""
        if recent_titles:
            diversity_note = (
                f" Also avoid picking something that is really just a "
                f"different angle on the same underlying technology or "
                f"product as any of these recently covered topics in this "
                f"same domain — a different feature of the same product "
                f"does not count as a new topic, even if the exact title "
                f"differs: {'; '.join(recent_titles)}."
            )
        return (
            f"Find one current, practical, hands-on topic in the domain "
            f"'{domain}' for a senior Python/AWS engineer. Exclude topics "
            f"matching these already-covered slugs: {exclusions}."
            f"{diversity_note} Use web search to ground the topic in "
            f"something current. "
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
