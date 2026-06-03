"""Tests du formatage des messages Slack (sans réseau)."""
from datetime import datetime, timedelta, timezone

import responses

from src.load.slack import _build_text, _format_distance, _format_duration


def test_format_distance_with_value():
    assert _format_distance(10879) == "10.9 km"
    assert _format_distance(1304) == "1.3 km"


def test_format_distance_none():
    # Cas escalade / yoga : pas de distance pertinente.
    assert _format_distance(None) == "session"


def test_format_duration_short():
    assert _format_duration(180) == "3 min"


def test_format_duration_with_hours():
    assert _format_duration(4617) == "1 h 16"


def test_build_text_contains_keypoints():
    start = datetime(2026, 5, 30, 9, 0, tzinfo=timezone.utc)
    end = start + timedelta(seconds=2700)  # 45 min
    msg = _build_text({
        "prenom": "Juliette",
        "nom": "Mendes",
        "sport_type": "Course à pied",
        "distance_m": 10800,
        "start_dt": start,
        "end_dt": end,
        "comment": None,
    })
    assert "Juliette" in msg and "Mendes" in msg
    assert "10.8 km" in msg
    assert "45 min" in msg


def test_build_text_appends_comment():
    start = datetime(2026, 5, 30, 17, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=4, minutes=52)
    msg = _build_text({
        "prenom": "Laurence",
        "nom": "Morvan",
        "sport_type": "Randonnée",
        "distance_m": 10000,
        "start_dt": start,
        "end_dt": end,
        "comment": "Randonnée de St Guilhem le désert, je vous la conseille",
    })
    assert 'St Guilhem' in msg
