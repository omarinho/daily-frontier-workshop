"""Researcher: picks today's domain and one deduped, hands-on topic.

Depends only on the injected :class:`ResearchClient` and :class:`TopicStore`
— never imports Compiler or Teacher directly (AC3/AC4/AC5 are unit-testable
without network access as a result).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path

from daily_workshop.constants import (
    DOMAIN_ROTATION_WINDOW,
    DOMAINS,
    MAX_KEY_FACTS,
    MIN_DOMAIN_APPEARANCES_IN_WINDOW,
    MIN_EXERCISE_WORDS,
    MIN_KEY_FACTS,
    RECENT_TITLES_CONTEXT_WINDOW,
    TOPIC_COOLDOWN_DAYS,
)
from daily_workshop.models import ResearchBrief
from daily_workshop.research_client import ResearchClient, ResearchClientError
from daily_workshop.text_utils import slugify
from daily_workshop.topic_store import TopicStore

logger = logging.getLogger(__name__)

DEFAULT_SEED_TOPICS_PATH: Path = Path(__file__).resolve().parent / "seed_topics.json"


class Researcher:
    """Selects a domain (rotation-fair) and a deduped topic within it."""

    def __init__(
        self,
        research_client: ResearchClient,
        topic_store: TopicStore,
        seed_topics_path: Path = DEFAULT_SEED_TOPICS_PATH,
        domains: tuple[str, ...] = DOMAINS,
        today: date | None = None,
    ) -> None:
        self._research_client = research_client
        self._topic_store = topic_store
        self._seed_topics_path = seed_topics_path
        self._domains = domains
        self._today = today or datetime.now(timezone.utc).astimezone().date()

    def run(self) -> ResearchBrief:
        history = self._topic_store.recent_domains()
        domain = self.select_domain(history, self._domains)
        self._log_domain_selection(domain, history)
        excluded_slugs = self._topic_store.covered_slugs_within(
            self._today, TOPIC_COOLDOWN_DAYS
        )
        recent_titles = tuple(
            self._topic_store.recent_summaries_for_domain(
                domain, RECENT_TITLES_CONTEXT_WINDOW
            )
        )

        brief = self._fetch_from_client(domain, excluded_slugs, recent_titles)

        if brief is not None and not self._meets_quality_bar(brief):
            logger.warning(
                "ResearchClient response for domain=%s failed the minimum "
                "quality bar (needs a real http(s) source link and a "
                "substantive, >= %d-word exercise) — it reads as a summary, "
                "not a hands-on brief. Falling back to seed backlog.",
                domain,
                MIN_EXERCISE_WORDS,
            )
            brief = None

        if brief is None or brief.slug in excluded_slugs:
            if brief is not None:
                logger.warning(
                    "ResearchClient returned already-covered slug=%s for "
                    "domain=%s; falling back to seed backlog.",
                    brief.slug,
                    domain,
                )
            brief = self._select_from_seed_backlog(domain, excluded_slugs)

        return self._ensure_source_links(self._normalize_key_facts(brief))

    @staticmethod
    def _meets_quality_bar(brief: ResearchBrief) -> bool:
        """Reject a live response that reads as a summary, not a hands-on brief.

        Two checks, both cheap proxies for "this is actually usable": a real
        http(s) source link (not empty, not a placeholder), and an exercise
        description substantial enough to plausibly be followable as steps
        rather than a one-line label.
        """
        has_real_source_link = any(
            link.startswith(("http://", "https://")) for link in brief.source_links
        )
        has_substantive_exercise = len(brief.exercise_idea.split()) >= MIN_EXERCISE_WORDS
        return has_real_source_link and has_substantive_exercise

    @staticmethod
    def _log_domain_selection(domain: str, history: list[str]) -> None:
        """Log why ``domain`` won today's rotation — visible via INFO logging.

        Two counts, for context: within the last DOMAIN_ROTATION_WINDOW
        selections (the AC3 policy's stated window) and over the entire
        history (what select_domain's greedy rule actually uses).
        """
        windowed = history[-DOMAIN_ROTATION_WINDOW:]
        windowed_counts = {d: windowed.count(d) for d in DOMAINS}
        lifetime_counts = {d: history.count(d) for d in DOMAINS}
        logger.info(
            "Domain selected: %s. Appearances in last %d runs: %s "
            "(policy: >= %d per domain). Lifetime counts: %s.",
            domain,
            DOMAIN_ROTATION_WINDOW,
            windowed_counts,
            MIN_DOMAIN_APPEARANCES_IN_WINDOW,
            lifetime_counts,
        )

    def _fetch_from_client(
        self,
        domain: str,
        excluded_slugs: set[str],
        recent_titles: tuple[str, ...] = (),
    ) -> ResearchBrief | None:
        try:
            return self._research_client.fetch_brief(
                domain, frozenset(excluded_slugs), recent_titles
            )
        except ResearchClientError as exc:
            logger.warning(
                "ResearchClient failed for domain=%s: %s. Falling back to "
                "seed backlog.",
                domain,
                exc,
            )
            return None

    @staticmethod
    def select_domain(history: list[str], domains: tuple[str, ...] = DOMAINS) -> str:
        """Choose the domain with the fewest past selections (fairness).

        Ties break by the domains' declared order, which — starting from an
        empty history — produces a stable round-robin cycle. This guarantees
        that over any 15 consecutive selections each of 3 domains is picked
        at least 4 times (AC3), and no domain can be starved indefinitely
        since its count only ever falls further behind the others.
        """
        counts = {domain: history.count(domain) for domain in domains}
        return min(domains, key=lambda domain: (counts[domain], domains.index(domain)))

    def _select_from_seed_backlog(
        self, domain: str, excluded_slugs: set[str]
    ) -> ResearchBrief:
        entries = self._load_seed_topics().get(domain, [])
        for entry in entries:
            slug = entry.get("slug") or slugify(entry["title"])
            if slug in excluded_slugs:
                continue
            return ResearchBrief(
                domain=domain,
                title=entry["title"],
                slug=slug,
                rationale=entry.get("rationale", entry["title"]),
                key_facts=tuple(entry.get("key_facts", ())),
                source_links=tuple(entry.get("source_links", ())),
                exercise_idea=entry.get("exercise_idea", ""),
            )
        raise ResearchClientError(
            f"No unused seed topics remain for domain={domain} "
            f"(all candidates are within the {TOPIC_COOLDOWN_DAYS}-day cooldown)."
        )

    def _load_seed_topics(self) -> dict[str, list[dict]]:
        return json.loads(self._seed_topics_path.read_text(encoding="utf-8"))

    @staticmethod
    def _normalize_key_facts(brief: ResearchBrief) -> ResearchBrief:
        """Clamp ``key_facts`` into the required [MIN_KEY_FACTS, MAX_KEY_FACTS] band."""
        facts = list(brief.key_facts)
        if len(facts) < MIN_KEY_FACTS:
            padding_source = facts or [brief.title]
            while len(facts) < MIN_KEY_FACTS:
                facts.append(padding_source[len(facts) % len(padding_source)])
        elif len(facts) > MAX_KEY_FACTS:
            facts = facts[:MAX_KEY_FACTS]

        if facts == list(brief.key_facts):
            return brief
        return dataclasses.replace(brief, key_facts=tuple(facts))

    @staticmethod
    def _ensure_source_links(brief: ResearchBrief) -> ResearchBrief:
        """Guarantee a non-empty ``source_links`` tuple (REQ-012 safety net).

        Seed backlog entries and ResearchClient responses are expected to
        carry at least one real reference link. If one is ever missing —
        e.g. a seed entry with ``"source_links": []`` — fall back to an
        honest, generic pointer rather than silently propagating an empty
        tuple into the resulting ResearchBrief. This is deliberately not a
        fabricated, specific-looking URL: it is an explicit instruction to
        go find one.
        """
        if brief.source_links:
            return brief
        logger.warning(
            "ResearchBrief slug=%s (domain=%s) has empty source_links; "
            "substituting a generic search pointer instead of propagating "
            "an empty tuple.",
            brief.slug,
            brief.domain,
        )
        return dataclasses.replace(
            brief, source_links=(f"search the web for: {brief.title}",)
        )
