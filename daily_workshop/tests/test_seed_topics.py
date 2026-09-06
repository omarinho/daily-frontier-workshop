# REQ-013: Seed topic backlog minimum content.
from __future__ import annotations

import json
from pathlib import Path

import daily_workshop
from daily_workshop.constants import DOMAINS
from daily_workshop.text_utils import slugify

_SEED_TOPICS_PATH = Path(daily_workshop.__file__).resolve().parent / "seed_topics.json"
_MIN_ENTRIES_PER_DOMAIN = 5


def _load_seed_topics() -> dict[str, list[dict]]:
    return json.loads(_SEED_TOPICS_PATH.read_text(encoding="utf-8"))


def test_at_least_5_seed_entries_per_domain() -> None:
    # TC-013-01
    data = _load_seed_topics()

    for domain in DOMAINS:
        assert domain in data, f"missing domain key {domain!r} in seed_topics.json"
        assert len(data[domain]) >= _MIN_ENTRIES_PER_DOMAIN, (
            f"domain {domain!r} has only {len(data[domain])} entries, "
            f"need >= {_MIN_ENTRIES_PER_DOMAIN}"
        )


def test_each_entry_has_unique_normalized_slug_title_and_domain() -> None:
    # TC-013-02
    data = _load_seed_topics()
    seen_slugs: set[str] = set()

    for domain in DOMAINS:
        for entry in data[domain]:
            assert entry["title"]
            assert entry["slug"]
            assert entry["slug"] == slugify(entry["title"])
            assert entry["slug"] not in seen_slugs, f"duplicate slug: {entry['slug']}"
            seen_slugs.add(entry["slug"])


def test_no_unexpected_domain_keys() -> None:
    data = _load_seed_topics()
    assert set(data.keys()) == set(DOMAINS)
