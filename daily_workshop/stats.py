"""Pure, offline aggregation over the covered-topics history.

No I/O here — :meth:`TopicStore.load_records` does the reading; this module
only aggregates and formats. ``python -m daily_workshop stats`` is the CLI
entrypoint (see ``__main__.py``). No dashboard, just visibility: domain
distribution, shortest/longest workshops, and any manually-recorded quality
ratings.
"""

from __future__ import annotations

from dataclasses import dataclass

from daily_workshop.constants import DOMAINS
from daily_workshop.models import TopicRecord


@dataclass(frozen=True)
class TopicStats:
    total_workshops: int
    by_domain: dict[str, int]
    never_covered_domains: tuple[str, ...]
    shortest: TopicRecord | None
    longest: TopicRecord | None
    average_word_count: float | None
    rated_count: int
    average_quality: float | None


def compute_stats(
    records: list[TopicRecord], domains: tuple[str, ...] = DOMAINS
) -> TopicStats:
    by_domain: dict[str, int] = dict.fromkeys(domains, 0)
    for record in records:
        by_domain[record.domain] = by_domain.get(record.domain, 0) + 1
    never_covered = tuple(domain for domain in domains if by_domain.get(domain) == 0)

    sized = [record for record in records if record.word_count > 0]
    shortest = min(sized, key=lambda r: r.word_count) if sized else None
    longest = max(sized, key=lambda r: r.word_count) if sized else None
    average_word_count = (
        sum(r.word_count for r in sized) / len(sized) if sized else None
    )

    rated = [record for record in records if record.quality is not None]
    average_quality = (
        sum(r.quality for r in rated if r.quality is not None) / len(rated)
        if rated
        else None
    )

    return TopicStats(
        total_workshops=len(records),
        by_domain=by_domain,
        never_covered_domains=never_covered,
        shortest=shortest,
        longest=longest,
        average_word_count=average_word_count,
        rated_count=len(rated),
        average_quality=average_quality,
    )


def format_stats(stats: TopicStats) -> str:
    lines = [f"Total workshops: {stats.total_workshops}", "", "By domain:"]
    for domain, count in stats.by_domain.items():
        lines.append(f"  {domain}: {count}")

    if stats.never_covered_domains:
        lines.append("")
        lines.append(f"Never covered yet: {', '.join(stats.never_covered_domains)}")

    if stats.average_word_count is not None and stats.shortest and stats.longest:
        lines.append("")
        lines.append(f"Average length: {stats.average_word_count:.0f} words")
        lines.append(
            f"  Shortest: {stats.shortest.word_count} words "
            f"({stats.shortest.date} — {stats.shortest.slug})"
        )
        lines.append(
            f"  Longest:  {stats.longest.word_count} words "
            f"({stats.longest.date} — {stats.longest.slug})"
        )

    lines.append("")
    if stats.rated_count:
        lines.append(
            f"Average quality: {stats.average_quality:.1f}/5 "
            f"(from {stats.rated_count} rated workshop(s))"
        )
    else:
        lines.append(
            "No quality ratings yet — hand-edit "
            "daily_workshop/data/covered_topics.json and set "
            '"quality": 1-5 on any entry to start tracking it here.'
        )

    return "\n".join(lines)
