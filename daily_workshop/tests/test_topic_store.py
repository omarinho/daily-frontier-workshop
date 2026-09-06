# REQ-008: Append-only, durable covered-topics history.
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

import pytest

from daily_workshop.models import TopicRecord
from daily_workshop.topic_store import TopicStore


def _read_raw(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_append_adds_exactly_one_new_well_formed_entry(tmp_path: Path) -> None:
    # TC-008-01
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)
    store.append(
        TopicRecord(date=date(2026, 1, 1), domain="agentic_ai", slug="a", summary="A")
    )

    store.append(
        TopicRecord(
            date=date(2026, 1, 2), domain="cloud_computing", slug="b", summary="B"
        )
    )

    raw = _read_raw(store_path)
    assert len(raw) == 2
    assert raw[0] == {
        "date": "2026-01-01",
        "domain": "agentic_ai",
        "slug": "a",
        "summary": "A",
        "word_count": 0,
        "quality": None,
    }
    assert raw[1] == {
        "date": "2026-01-02",
        "domain": "cloud_computing",
        "slug": "b",
        "summary": "B",
        "word_count": 0,
        "quality": None,
    }


def test_append_leaves_prior_entries_unchanged(tmp_path: Path) -> None:
    # TC-008-01
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)
    store.append(
        TopicRecord(date=date(2026, 1, 1), domain="agentic_ai", slug="a", summary="A")
    )
    before = _read_raw(store_path)

    store.append(
        TopicRecord(
            date=date(2026, 1, 5), domain="quantum_computing", slug="c", summary="C"
        )
    )

    after = _read_raw(store_path)
    assert after[0] == before[0]
    assert len(after) == len(before) + 1


def test_failure_between_temp_write_and_rename_leaves_original_uncorrupted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # TC-008-02
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)
    store.append(
        TopicRecord(date=date(2026, 1, 1), domain="agentic_ai", slug="a", summary="A")
    )
    original_raw = store_path.read_text(encoding="utf-8")

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise OSError("simulated crash between temp-write and rename")

    monkeypatch.setattr(os, "replace", _boom)

    with pytest.raises(OSError):
        store.append(
            TopicRecord(
                date=date(2026, 1, 2), domain="cloud_computing", slug="b", summary="B"
            )
        )

    assert store_path.read_text(encoding="utf-8") == original_raw
    assert json.loads(original_raw) == [
        {
            "date": "2026-01-01",
            "domain": "agentic_ai",
            "slug": "a",
            "summary": "A",
            "word_count": 0,
            "quality": None,
        }
    ]


def test_load_records_returns_empty_list_when_no_file_yet(tmp_path: Path) -> None:
    store = TopicStore(tmp_path / "does-not-exist.json")
    assert store.load_records() == []


def test_covered_slugs_within_excludes_recent_and_includes_old(tmp_path: Path) -> None:
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)
    store.append(
        TopicRecord(
            date=date(2026, 1, 1), domain="agentic_ai", slug="recent", summary="R"
        )
    )

    covered = store.covered_slugs_within(as_of=date(2026, 1, 10), cooldown_days=90)

    assert covered == {"recent"}


def test_word_count_and_quality_round_trip(tmp_path: Path) -> None:
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)

    store.append(
        TopicRecord(
            date=date(2026, 1, 1),
            domain="agentic_ai",
            slug="a",
            summary="A",
            word_count=414,
            quality=4,
        )
    )

    records = store.load_records()
    assert records[0].word_count == 414
    assert records[0].quality == 4


def test_loading_pre_existing_history_without_word_count_or_quality_keys(
    tmp_path: Path,
) -> None:
    # Backward compatibility: history written before this feature existed
    # has neither key — must load, not raise KeyError.
    store_path = tmp_path / "covered_topics.json"
    store_path.write_text(
        json.dumps(
            [{"date": "2026-01-01", "domain": "agentic_ai", "slug": "a", "summary": "A"}]
        ),
        encoding="utf-8",
    )
    store = TopicStore(store_path)

    records = store.load_records()

    assert records[0].word_count == 0
    assert records[0].quality is None


def test_recent_domains_returns_domains_oldest_first(tmp_path: Path) -> None:
    store_path = tmp_path / "covered_topics.json"
    store = TopicStore(store_path)
    store.append(
        TopicRecord(date=date(2026, 1, 1), domain="agentic_ai", slug="a", summary="A")
    )
    store.append(
        TopicRecord(
            date=date(2026, 1, 2), domain="quantum_computing", slug="b", summary="B"
        )
    )

    assert store.recent_domains() == ["agentic_ai", "quantum_computing"]
