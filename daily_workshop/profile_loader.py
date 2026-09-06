"""Loads the learner's :class:`PersonalizationProfile` from a TOML file.

Externalizing personalization (rather than hardcoding it in compiler.py)
means a clone with a different learner — or the same learner adopting a new
stack — is a one-file edit, not a code change. Uses ``tomllib`` (stdlib,
Python 3.11+, read-only) so this stays a zero-dependency project.
"""

from __future__ import annotations

import logging
from pathlib import Path

import tomllib

from daily_workshop.models import PersonalizationProfile

logger = logging.getLogger(__name__)

DEFAULT_PROFILE_PATH: Path = (
    Path(__file__).resolve().parent.parent / "inputs" / "profile.toml"
)

# Used only if inputs/profile.toml is missing or a field is omitted from it.
# Deliberately conservative (assumes nothing about the learner's background)
# rather than mirroring any one person's real stack.
FALLBACK_PROFILE = PersonalizationProfile(
    preferred_language="python",
    preferred_cloud="aws",
    known_technologies=(),
    linting_tools=(),
    formatter="black",
    quantum_comfort="none",
    agentic_framework_familiarity=False,
    constraints=(),
)


def load_personalization_profile(
    path: Path = DEFAULT_PROFILE_PATH,
) -> PersonalizationProfile:
    """Read ``path`` (TOML) into a :class:`PersonalizationProfile`.

    Missing file or missing individual fields fall back to
    :data:`FALLBACK_PROFILE` — personalization is a nice-to-have, never a
    hard dependency for a run to succeed. Logs a warning when the file is
    missing entirely, so an accidental delete is visible, not silent.
    """
    if not path.exists():
        logger.warning(
            "%s not found; using conservative built-in personalization "
            "defaults. Create it (see inputs/profile.toml in the repo) to "
            "personalize workshops for your own background.",
            path,
        )
        return FALLBACK_PROFILE

    with path.open("rb") as handle:
        data = tomllib.load(handle)

    return PersonalizationProfile(
        preferred_language=data.get(
            "preferred_language", FALLBACK_PROFILE.preferred_language
        ),
        preferred_cloud=data.get("preferred_cloud", FALLBACK_PROFILE.preferred_cloud),
        known_technologies=tuple(data.get("known_technologies", ())),
        linting_tools=tuple(data.get("linting_tools", ())),
        formatter=data.get("formatter", FALLBACK_PROFILE.formatter),
        quantum_comfort=data.get("quantum_comfort", FALLBACK_PROFILE.quantum_comfort),
        agentic_framework_familiarity=bool(
            data.get("agentic_framework_familiarity", False)
        ),
        constraints=tuple(data.get("constraints", ())),
    )
