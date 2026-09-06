# Personalization externalized to inputs/profile.toml (no code change to
# personalize) — see profile_loader.py.
from __future__ import annotations

from pathlib import Path

from daily_workshop.profile_loader import FALLBACK_PROFILE, load_personalization_profile


def _write_profile(tmp_path: Path, contents: str) -> Path:
    path = tmp_path / "profile.toml"
    path.write_text(contents, encoding="utf-8")
    return path


def test_missing_file_falls_back_to_conservative_default(tmp_path: Path) -> None:
    profile = load_personalization_profile(tmp_path / "does-not-exist.toml")
    assert profile == FALLBACK_PROFILE


def test_loads_all_fields_from_toml(tmp_path: Path) -> None:
    path = _write_profile(
        tmp_path,
        """
        preferred_language = "python"
        preferred_cloud = "gcp"
        known_technologies = ["docker", "kubernetes"]
        linting_tools = ["ruff"]
        formatter = "black"
        quantum_comfort = "practical"
        agentic_framework_familiarity = true
        constraints = ["no_gpu", "local_only"]
        """,
    )

    profile = load_personalization_profile(path)

    assert profile.preferred_language == "python"
    assert profile.preferred_cloud == "gcp"
    assert profile.known_technologies == ("docker", "kubernetes")
    assert profile.linting_tools == ("ruff",)
    assert profile.formatter == "black"
    assert profile.quantum_comfort == "practical"
    assert profile.agentic_framework_familiarity is True
    assert profile.constraints == ("no_gpu", "local_only")


def test_missing_individual_fields_fall_back_per_field(tmp_path: Path) -> None:
    # Only preferred_cloud set — everything else should use FALLBACK_PROFILE.
    path = _write_profile(tmp_path, 'preferred_cloud = "azure"\n')

    profile = load_personalization_profile(path)

    assert profile.preferred_cloud == "azure"
    assert profile.preferred_language == FALLBACK_PROFILE.preferred_language
    assert profile.quantum_comfort == FALLBACK_PROFILE.quantum_comfort
    assert profile.constraints == FALLBACK_PROFILE.constraints
