"""Invariants du générateur d'activités."""
from datetime import datetime, timezone

import numpy as np
import pytest

from src.generate.activities import (
    SPORT_PROFILES,
    SPORT_TO_STRAVA,
    _normalize_sport,
    _to_strava_payload,
)


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


def test_strava_mapping_covers_all_sports():
    """Chaque sport déclarable a un sport_type Strava — sinon KeyError en prod."""
    assert set(SPORT_TO_STRAVA) == set(SPORT_PROFILES)


def test_strava_payload_structure():
    """Le payload respecte le contrat de l'API Strava (clés + types)."""
    start = datetime(2025, 6, 1, 8, 30, tzinfo=timezone.utc)
    payload = _to_strava_payload(
        activity_id=10000000001,
        emp_id=43015,
        sport="Course à pied",
        dist_m=10879,
        elapsed_s=4617,
        moving_s=4200,
        start=start,
    )
    assert payload["id"] == 10000000001
    assert payload["athlete"] == {"id": 43015}
    assert payload["sport_type"] == "Run"
    assert payload["name"] == "Course à pied"        # libellé FR conservé
    assert payload["distance"] == 10879
    # Invariant Strava fondamental : moving_time <= elapsed_time.
    assert payload["moving_time"] <= payload["elapsed_time"]
    assert payload["start_date"].endswith("Z")        # UTC
    # Heure locale Paris : +02:00 en été (CEST), +01:00 en hiver (CET).
    assert payload["start_date_local"].endswith(("+01:00", "+02:00"))


def test_strava_payload_distance_none_for_climbing():
    """Sports sans distance (escalade) → distance null dans le payload."""
    start = datetime(2025, 6, 1, 17, 0, tzinfo=timezone.utc)
    payload = _to_strava_payload(
        activity_id=10000000002,
        emp_id=35731,
        sport="Escalade",
        dist_m=None,
        elapsed_s=6000,
        moving_s=5400,
        start=start,
    )
    assert payload["distance"] is None
    assert payload["sport_type"] == "RockClimbing"
