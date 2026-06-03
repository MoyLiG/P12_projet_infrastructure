"""Invariants du générateur d'activités."""
import numpy as np
import pytest

from src.generate.activities import SPORT_PROFILES, _normalize_sport


def test_sport_normalization_canonical():
    assert _normalize_sport("Course à pied") == "Course à pied"
    assert _normalize_sport("course à pied") == "Course à pied"


def test_sport_normalization_synonyms():
    assert _normalize_sport("running") == "Course à pied"
    assert _normalize_sport("velo") == "Vélo"
    assert _normalize_sport("foot") == "Football"


def test_sport_normalization_unknown_returns_none():
    assert _normalize_sport("ping-pong souterrain") is None
    assert _normalize_sport(None) is None


def test_sport_profile_distance_positive():
    rng = np.random.default_rng(42)
    for label, profile in SPORT_PROFILES.items():
        dist, dur = profile.sample(rng)
        if profile.distance_mu is not None:
            assert dist is not None and dist >= 0, f"distance négative pour {label}"
        else:
            assert dist is None, f"{label} devrait avoir distance NULL"
        assert dur > 0


def test_running_distance_realistic():
    """Course à pied : distance moyenne entre 3 et 20 km sur 1000 samples."""
    rng = np.random.default_rng(42)
    profile = SPORT_PROFILES["Course à pied"]
    distances_km = [profile.sample(rng)[0] / 1000 for _ in range(1000)]
    mean = sum(distances_km) / len(distances_km)
    assert 5 <= mean <= 15, f"Moyenne course à pied irréaliste : {mean:.1f} km"
