# Visibility over the covered-topics history: domain distribution,
# shortest/longest workshops, manually-recorded quality — no dashboard,
# just `python -m daily_workshop stats`.
from __future__ import annotations

from datetime import date

from daily_workshop.models import TopicRecord
from daily_workshop.stats import compute_stats, format_stats


def _record(**overrides: object) -> TopicRecord:
    defaults: dict[str, object] = {
        "date": date(2026, 1, 1),
        "domain": "agentic_ai",
        "slug": "a",
        "summary": "A",
        "word_count": 500,
        "quality": None,
    }
    defaults.update(overrides)
    return TopicRecord(**defaults)  # type: ignore[arg-type]


def test_empty_history_reports_zero_and_all_domains_never_covered() -> None:
    stats = compute_stats([])

    assert stats.total_workshops == 0
    assert set(stats.never_covered_domains) == {
        "agentic_ai",
        "cloud_computing",
        "quantum_computing",
    }
    assert stats.average_word_count is None
    assert stats.rated_count == 0


def test_counts_by_domain() -> None:
    records = [
        _record(domain="agentic_ai"),
        _record(domain="agentic_ai"),
        _record(domain="cloud_computing"),
    ]

    stats = compute_stats(records)

    assert stats.by_domain == {
        "agentic_ai": 2,
        "cloud_computing": 1,
        "quantum_computing": 0,
    }
    assert stats.never_covered_domains == ("quantum_computing",)


def test_shortest_and_longest_by_word_count() -> None:
    records = [
        _record(slug="short", word_count=300),
        _record(slug="long", word_count=1200),
        _record(slug="mid", word_count=700),
    ]

    stats = compute_stats(records)

    assert stats.shortest is not None and stats.shortest.slug == "short"
    assert stats.longest is not None and stats.longest.slug == "long"
    assert stats.average_word_count == (300 + 1200 + 700) / 3


def test_records_with_zero_word_count_excluded_from_length_stats() -> None:
    # Pre-existing history from before word_count was tracked has 0 — must
    # not skew average/shortest toward a value that was never real.
    records = [_record(word_count=0), _record(word_count=800)]

    stats = compute_stats(records)

    assert stats.average_word_count == 800
    assert stats.shortest is not None and stats.shortest.word_count == 800


def test_average_quality_only_over_rated_records() -> None:
    records = [
        _record(quality=5),
        _record(quality=3),
        _record(quality=None),
    ]

    stats = compute_stats(records)

    assert stats.rated_count == 2
    assert stats.average_quality == 4.0


def test_format_stats_mentions_never_covered_domain() -> None:
    stats = compute_stats([_record(domain="agentic_ai")])
    output = format_stats(stats)
    assert "quantum_computing" in output
    assert "cloud_computing" in output


def test_format_stats_without_ratings_explains_how_to_add_them() -> None:
    stats = compute_stats([_record()])
    output = format_stats(stats)
    assert "quality" in output.lower()


def test_format_stats_with_ratings_shows_average() -> None:
    stats = compute_stats([_record(quality=4), _record(quality=2)])
    output = format_stats(stats)
    assert "3.0/5" in output
