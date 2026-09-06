# REQ-003, REQ-004, REQ-005, REQ-012: domain rotation, 90-day dedup, backlog
# fallback, and research-brief shape.
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import pytest

from daily_workshop.constants import (
    DOMAINS,
    MAX_KEY_FACTS,
    MIN_KEY_FACTS,
    TOPIC_COOLDOWN_DAYS,
)
from daily_workshop.models import ResearchBrief, TopicRecord
from daily_workshop.research_client import ResearchClientError
from daily_workshop.researcher import DEFAULT_SEED_TOPICS_PATH, Researcher
from daily_workshop.tests.fakes import (
    EmptyResearchClient,
    FailingResearchClient,
    FakeResearchClient,
)
from daily_workshop.topic_store import TopicStore

_SEED_TOPICS = {
    "agentic_ai": [
        {"title": "Seed A1", "slug": "seed-a1", "key_facts": ["f1", "f2", "f3"]},
        {"title": "Seed A2", "slug": "seed-a2", "key_facts": ["f1", "f2", "f3"]},
    ],
    "cloud_computing": [
        {"title": "Seed C1", "slug": "seed-c1", "key_facts": ["f1", "f2", "f3"]},
        {"title": "Seed C2", "slug": "seed-c2", "key_facts": ["f1", "f2", "f3"]},
    ],
    "quantum_computing": [
        {"title": "Seed Q1", "slug": "seed-q1", "key_facts": ["f1", "f2", "f3"]},
        {"title": "Seed Q2", "slug": "seed-q2", "key_facts": ["f1", "f2", "f3"]},
    ],
}


def _write_seed_topics(tmp_path: Path, data: dict = _SEED_TOPICS) -> Path:
    path = tmp_path / "seed_topics.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _brief(
    domain: str = "agentic_ai", slug: str = "topic-x", **overrides: object
) -> ResearchBrief:
    defaults: dict[str, object] = {
        "domain": domain,
        "title": "Topic X",
        "slug": slug,
        "rationale": "Because it matters.",
        "key_facts": ("fact 1", "fact 2", "fact 3"),
        "source_links": ("https://example.com",),
        "exercise_idea": (
            "Implement a small working example of the concept and verify "
            "its output against the expected result."
        ),
    }
    defaults.update(overrides)
    return ResearchBrief(**defaults)  # type: ignore[arg-type]


# ─── TC-003: domain rotation fairness ──────────────────────────────────────


def test_select_domain_picks_least_selected_domain_from_empty_history() -> None:
    assert Researcher.select_domain([], DOMAINS) == DOMAINS[0]


def test_select_domain_over_15_runs_gives_each_domain_at_least_4() -> None:
    # TC-003-01
    history: list[str] = []
    for _ in range(15):
        chosen = Researcher.select_domain(history, DOMAINS)
        history.append(chosen)

    counts = {domain: history.count(domain) for domain in DOMAINS}
    for domain in DOMAINS:
        assert counts[domain] >= 4, counts


@pytest.mark.parametrize(
    "starting_history",
    [
        [],
        ["agentic_ai"] * 10,
        ["cloud_computing"] * 5 + ["quantum_computing"] * 5,
        ["agentic_ai", "agentic_ai", "cloud_computing"],
    ],
)
def test_select_domain_never_starves_a_domain_indefinitely(
    starting_history: list[str],
) -> None:
    # TC-003-03
    history = list(starting_history)
    selections: list[str] = []
    for _ in range(30):
        chosen = Researcher.select_domain(history, DOMAINS)
        history.append(chosen)
        selections.append(chosen)

    for domain in DOMAINS:
        assert domain in selections, f"{domain} was starved over 30 selections"


def test_rotation_persists_across_fresh_researcher_instances(tmp_path: Path) -> None:
    # TC-003-02
    # Rotation history is persisted via TopicStore (populated by Teacher in
    # the real pipeline) — a fresh Researcher instance must read that same
    # persisted history rather than keeping any in-memory state of its own.
    from daily_workshop.models import TopicRecord

    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    fixed_today = date(2026, 1, 1)

    selected_domains: list[str] = []
    for _ in range(6):
        researcher = Researcher(
            research_client=EmptyResearchClient(),
            topic_store=topic_store,
            seed_topics_path=seed_path,
            today=fixed_today,
        )
        brief = researcher.run()
        selected_domains.append(brief.domain)
        # Simulate Teacher recording the run, as the real pipeline does.
        topic_store.append(
            TopicRecord(
                date=fixed_today, domain=brief.domain, slug=brief.slug, summary="s"
            )
        )
        fixed_today += timedelta(days=1)

    counts = {domain: selected_domains.count(domain) for domain in DOMAINS}
    assert counts == {domain: 2 for domain in DOMAINS}


# ─── TC-004: 90-day dedup ───────────────────────────────────────────────────


def test_excluded_slug_dated_10_days_ago_is_not_selected_from_backlog(
    tmp_path: Path,
) -> None:
    # TC-004-01
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    from daily_workshop.models import TopicRecord

    topic_store.append(
        TopicRecord(
            date=today - timedelta(days=10),
            domain="agentic_ai",
            slug="seed-a1",
            summary="s",
        )
    )
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=today,
    )

    brief = researcher._select_from_seed_backlog(
        "agentic_ai", topic_store.covered_slugs_within(today, TOPIC_COOLDOWN_DAYS)
    )

    assert brief.slug != "seed-a1"
    assert brief.slug == "seed-a2"


def test_slug_dated_91_days_ago_is_eligible_again(tmp_path: Path) -> None:
    # TC-004-02 [inferred]
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    from daily_workshop.models import TopicRecord

    topic_store.append(
        TopicRecord(
            date=today - timedelta(days=91),
            domain="agentic_ai",
            slug="seed-a1",
            summary="s",
        )
    )
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=today,
    )

    brief = researcher._select_from_seed_backlog(
        "agentic_ai", topic_store.covered_slugs_within(today, TOPIC_COOLDOWN_DAYS)
    )

    assert brief.slug == "seed-a1"


@pytest.mark.parametrize(
    ("age_days", "expect_excluded"),
    [
        (89, True),
        (90, False),
        (91, False),
    ],
)
def test_cooldown_boundary_at_exactly_topic_cooldown_days(
    tmp_path: Path, age_days: int, expect_excluded: bool
) -> None:
    # TC-004-03 [inferred]
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    from daily_workshop.models import TopicRecord

    topic_store.append(
        TopicRecord(
            date=today - timedelta(days=age_days),
            domain="agentic_ai",
            slug="seed-a1",
            summary="s",
        )
    )

    covered = topic_store.covered_slugs_within(today, TOPIC_COOLDOWN_DAYS)

    assert ("seed-a1" in covered) is expect_excluded


# ─── TC-005: backlog fallback on research failure ──────────────────────────


def test_failing_research_client_falls_back_to_seed_backlog(tmp_path: Path) -> None:
    # TC-005-01
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.slug in {"seed-a1", "seed-a2"}


def test_empty_research_client_response_falls_back_to_seed_backlog(
    tmp_path: Path,
) -> None:
    # TC-005-02
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=EmptyResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.slug in {"seed-a1", "seed-a2"}


def test_fallback_is_explicitly_logged_not_silent(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    # TC-005-03
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient("boom"),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    with caplog.at_level(logging.WARNING):
        researcher.run()

    assert any("fall" in record.message.lower() for record in caplog.records)


# ─── Minimum brief quality gate (hardened Researcher contract) ─────────────


def test_thin_exercise_from_live_client_falls_back_to_seed_backlog(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(_brief(exercise_idea="Do it.")),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    with caplog.at_level(logging.WARNING):
        brief = researcher.run()

    assert brief.slug.startswith("seed-")
    assert any("quality bar" in record.message for record in caplog.records)


def test_no_real_source_link_from_live_client_falls_back_to_seed_backlog(
    tmp_path: Path,
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(
            _brief(source_links=("search the web for: Topic X",))
        ),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.slug.startswith("seed-")


def test_substantive_exercise_and_real_link_pass_the_quality_bar(
    tmp_path: Path,
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(_brief()),  # fixture default qualifies
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.slug == "topic-x"  # came from the live client, not the seed backlog


def test_bundled_seed_topics_all_pass_the_live_quality_bar() -> None:
    # The fallback data must itself be good enough that falling back never
    # silently downgrades quality — reuses the real bundled file, not the
    # small fixture above.
    from daily_workshop.researcher import DEFAULT_SEED_TOPICS_PATH

    seed_data = json.loads(DEFAULT_SEED_TOPICS_PATH.read_text(encoding="utf-8"))
    for domain, entries in seed_data.items():
        for entry in entries:
            exercise_idea = entry.get("exercise_idea", "")
            assert len(exercise_idea.split()) >= 8, (
                f"{domain}/{entry.get('slug')} exercise_idea is too thin to "
                f"pass the live quality bar"
            )
            source_links = entry.get("source_links", [])
            assert any(
                link.startswith(("http://", "https://")) for link in source_links
            ), f"{domain}/{entry.get('slug')} has no real http(s) source link"


# ─── Topical diversity within a domain ─────────────────────────────────────


def test_recent_same_domain_titles_are_passed_to_the_research_client(
    tmp_path: Path,
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    topic_store.append(
        TopicRecord(
            date=date(2026, 1, 1), domain="agentic_ai", slug="a", summary="Topic A"
        )
    )
    topic_store.append(
        TopicRecord(
            date=date(2026, 1, 2),
            domain="cloud_computing",
            slug="c",
            summary="Topic C",
        )
    )
    # Tie every domain's count at 1 so select_domain's tie-break (declared
    # order) picks agentic_ai — otherwise the greedy least-selected rule
    # would pick quantum_computing (count 0) instead.
    topic_store.append(
        TopicRecord(
            date=date(2026, 1, 3),
            domain="quantum_computing",
            slug="q",
            summary="Topic Q",
        )
    )
    seed_path = _write_seed_topics(tmp_path)
    client = FakeResearchClient(_brief())
    researcher = Researcher(
        research_client=client,
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 10),
    )

    researcher.run()

    assert client.last_call is not None
    _, _, recent_titles = client.last_call
    assert recent_titles == ("Topic A",)  # only the same-domain (agentic_ai) one


def test_no_history_passes_empty_recent_titles(tmp_path: Path) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    client = FakeResearchClient(_brief())
    researcher = Researcher(
        research_client=client,
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    researcher.run()

    assert client.last_call is not None
    assert client.last_call[2] == ()


# ─── Domain-selection visibility (configurable rotation policy) ───────────


def test_domain_selection_is_logged_with_counts(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(_brief()),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    with caplog.at_level(logging.INFO):
        researcher.run()

    messages = [record.message for record in caplog.records]
    assert any("Domain selected:" in message for message in messages)
    assert any("agentic_ai" in message for message in messages)


def test_fallback_still_respects_90_day_dedup(tmp_path: Path) -> None:
    # TC-005-04 [inferred]
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    from daily_workshop.models import TopicRecord

    topic_store.append(
        TopicRecord(
            date=today - timedelta(days=5),
            domain="agentic_ai",
            slug="seed-a1",
            summary="s",
        )
    )
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=today,
    )

    excluded = topic_store.covered_slugs_within(today, TOPIC_COOLDOWN_DAYS)
    brief = researcher._select_from_seed_backlog("agentic_ai", excluded)

    assert brief.slug == "seed-a2"


def test_research_client_returning_already_covered_slug_falls_back(
    tmp_path: Path,
) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    from daily_workshop.models import TopicRecord

    topic_store.append(
        TopicRecord(
            date=today - timedelta(days=5),
            domain="agentic_ai",
            slug="dup-topic",
            summary="s",
        )
    )
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(
            _brief(domain="agentic_ai", slug="dup-topic")
        ),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=today,
    )

    brief = researcher.run()

    assert brief.slug != "dup-topic"


def test_no_unused_seed_topics_raises_research_client_error(tmp_path: Path) -> None:
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    today = date(2026, 1, 20)
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=today,
    )

    with pytest.raises(ResearchClientError):
        researcher._select_from_seed_backlog("agentic_ai", {"seed-a1", "seed-a2"})


# ─── TC-012: research brief shape ───────────────────────────────────────────


def test_research_brief_has_non_empty_required_fields(tmp_path: Path) -> None:
    # TC-012-01
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(_brief()),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.title
    assert brief.rationale
    assert brief.source_links
    assert brief.exercise_idea
    assert len(brief.key_facts) > 0


def test_seed_backlog_entry_with_empty_source_links_gets_fallback_pointer(
    tmp_path: Path,
) -> None:
    # TC-012-03 [inferred] — REQ-012 remediation round 1: a seed backlog
    # entry with "source_links": [] (as several bundled entries in the real
    # seed_topics.json used to have) must not propagate an empty tuple into
    # the resulting ResearchBrief; Researcher must substitute an honest,
    # generic pointer instead.
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_data = {
        "agentic_ai": [
            {
                "title": "No Links Seed",
                "slug": "no-links-seed",
                "key_facts": ["f1", "f2", "f3"],
                "source_links": [],
            },
        ],
        "cloud_computing": [
            {"title": "Seed C1", "slug": "seed-c1", "key_facts": ["f1", "f2", "f3"]},
        ],
        "quantum_computing": [
            {"title": "Seed Q1", "slug": "seed-q1", "key_facts": ["f1", "f2", "f3"]},
        ],
    }
    seed_path = _write_seed_topics(tmp_path, seed_data)
    researcher = Researcher(
        research_client=FailingResearchClient(),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert brief.slug == "no-links-seed"
    assert brief.source_links
    assert brief.source_links == ("search the web for: No Links Seed",)


def test_bundled_seed_topics_all_have_source_links() -> None:
    # TC-012-04 [inferred] — REQ-012 fix #1: every entry in the real, bundled
    # seed_topics.json must carry at least one real reference link, so the
    # fallback in _ensure_source_links is a safety net, not the everyday
    # path.
    real_seed_path = DEFAULT_SEED_TOPICS_PATH
    real_topics = json.loads(real_seed_path.read_text(encoding="utf-8"))
    for domain, entries in real_topics.items():
        for entry in entries:
            assert entry.get(
                "source_links"
            ), f"{domain}/{entry.get('slug')} has no source_links"


@pytest.mark.parametrize(
    ("input_key_facts", "expected_len"),
    [
        ((), MIN_KEY_FACTS),
        (("only one",), MIN_KEY_FACTS),
        (("a", "b", "c"), 3),
        (("a", "b", "c", "d", "e"), MAX_KEY_FACTS),
        (("a", "b", "c", "d", "e", "f", "g"), MAX_KEY_FACTS),
    ],
)
def test_key_facts_length_normalized_within_band(
    tmp_path: Path, input_key_facts: tuple[str, ...], expected_len: int
) -> None:
    # TC-012-02
    topic_store = TopicStore(tmp_path / "covered_topics.json")
    seed_path = _write_seed_topics(tmp_path)
    researcher = Researcher(
        research_client=FakeResearchClient(_brief(key_facts=input_key_facts)),
        topic_store=topic_store,
        seed_topics_path=seed_path,
        today=date(2026, 1, 1),
    )

    brief = researcher.run()

    assert len(brief.key_facts) == expected_len
    assert MIN_KEY_FACTS <= len(brief.key_facts) <= MAX_KEY_FACTS
