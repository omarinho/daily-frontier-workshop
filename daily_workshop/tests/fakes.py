"""Fakes/mocks for ResearchClient, shared across test modules.

Never inline a lambda/mock scattered across test files for this — everything
that stands in for a real ResearchClient lives here (see
``inputs/code-style-guides/backend.md`` "Naming Conventions").
"""

from __future__ import annotations

from daily_workshop.models import ResearchBrief
from daily_workshop.research_client import ResearchClient, ResearchClientError


class FakeResearchClient(ResearchClient):
    """Returns a fixed, pre-built ResearchBrief. No network access."""

    def __init__(self, brief: ResearchBrief | None) -> None:
        self._brief = brief

    def fetch_brief(
        self, domain: str, excluded_slugs: frozenset[str]
    ) -> ResearchBrief | None:
        return self._brief


class FailingResearchClient(ResearchClient):
    """Always raises ResearchClientError. No network access."""

    def __init__(self, message: str = "simulated research failure") -> None:
        self._message = message

    def fetch_brief(
        self, domain: str, excluded_slugs: frozenset[str]
    ) -> ResearchBrief | None:
        raise ResearchClientError(self._message)


class EmptyResearchClient(ResearchClient):
    """Always returns None (research "succeeded" but found nothing usable)."""

    def fetch_brief(
        self, domain: str, excluded_slugs: frozenset[str]
    ) -> ResearchBrief | None:
        return None
