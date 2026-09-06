"""Repository-pattern-lite persistence for the covered-topics history (AC8).

All reads/writes to the covered-topics JSON file go through this class — no
other module touches that file directly. Writes are atomic (write-temp,
then ``os.replace``) so a crash mid-write can never corrupt prior history.

The store's default location lives inside this package's own ``data/``
directory — never inside the repo-root ``memory/`` directory, which is this
TDD framework's own unrelated knowledge base (see
``inputs/INSTRUCTIONS.md`` "Additional Notes").
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from daily_workshop.models import TopicRecord

DEFAULT_TOPIC_STORE_PATH: Path = (
    Path(__file__).resolve().parent / "data" / "covered_topics.json"
)


class TopicStore:
    """Append-only, durable history of previously covered topics."""

    def __init__(self, path: Path = DEFAULT_TOPIC_STORE_PATH) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def load_records(self) -> list[TopicRecord]:
        """Return all recorded entries, oldest first. Empty list if no file yet."""
        if not self._path.exists():
            return []
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        return [
            TopicRecord(
                date=date.fromisoformat(entry["date"]),
                domain=entry["domain"],
                slug=entry["slug"],
                summary=entry["summary"],
                # .get() with a default: entries written before word_count/
                # quality existed have neither key — old history must still
                # load, not raise KeyError.
                word_count=entry.get("word_count", 0),
                quality=entry.get("quality"),
            )
            for entry in raw
        ]

    def covered_slugs_within(self, as_of: date, cooldown_days: int) -> set[str]:
        """Slugs whose age (in days, relative to ``as_of``) is < ``cooldown_days``.

        A record dated exactly ``cooldown_days`` ago (or earlier) is
        considered eligible again — the cooldown window is a half-open
        interval ``[0, cooldown_days)``.
        """
        return {
            record.slug
            for record in self.load_records()
            if (as_of - record.date).days < cooldown_days
        }

    def recent_domains(self) -> list[str]:
        """Domains of every recorded entry, oldest first."""
        return [record.domain for record in self.load_records()]

    def recent_summaries_for_domain(self, domain: str, limit: int) -> list[str]:
        """The last ``limit`` summaries recorded for ``domain``, newest first.

        Used to give the live research prompt topical-diversity context —
        slug-based dedup only blocks an exact repeat; this lets the prompt
        avoid re-covering the same underlying technology/product under a
        different title (see RECENT_TITLES_CONTEXT_WINDOW).
        """
        matching = [r.summary for r in self.load_records() if r.domain == domain]
        return list(reversed(matching[-limit:]))

    def append(self, record: TopicRecord) -> None:
        """Add exactly one new entry, atomically, preserving prior history.

        Writes to a sibling temp file first, then ``os.replace``s it over the
        real path — an interruption between those two steps leaves the
        original file exactly as it was.
        """
        existing_raw = (
            json.loads(self._path.read_text(encoding="utf-8"))
            if self._path.exists()
            else []
        )
        existing_raw.append(
            {
                "date": record.date.isoformat(),
                "domain": record.domain,
                "slug": record.slug,
                "summary": record.summary,
                "word_count": record.word_count,
                "quality": record.quality,
            }
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        temp_path.write_text(json.dumps(existing_raw, indent=2), encoding="utf-8")
        os.replace(temp_path, self._path)
