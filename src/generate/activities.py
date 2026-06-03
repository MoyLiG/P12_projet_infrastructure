"""
Générateur d'activités sportives au format de l'API Strava.

Spec :
- Crée ~settings.activities_total enregistrements sur les 12 derniers mois.
- Chaque salarié ayant une `sport_pratique` reçoit un nombre d'activités
  tiré d'une loi de Poisson centrée sur 25/an → distribution réaliste
  (certains salariés autour de 5, d'autres autour de 50).
- Le `sport_type` de chaque activité reste cohérent avec ce qu'il pratique.
- Distance et durée tirées de distributions par sport (cf. SPORT_PROFILES).
- Seed fixe (settings.activities_seed) → reproductibilité totale.

Pourquoi produire un payload "façon API Strava" plutôt que des colonnes plates ?
→ La couche `raw` reflète ce qu'une source tierce renverrait réellement
  (JSON imbriqué : `athlete`, `moving_time` ≠ `elapsed_time`, `start_date`
  vs `start_date_local`…). Le pipeline aplatit ensuite ce JSON vers
  `staging.activities` (src/transform/activities.py). Le jour d'un branchement
  sur la vraie API Strava, seule l'alimentation de `raw.activities` change ;
  l'aplatissement et tout l'aval restent identiques.

Pourquoi un générateur "intelligent" plutôt que random pur ?
→ Évite l'incohérence ("salarié escaladeur qui fait 12 km de course") qui
  rendrait le POC ridicule en soutenance.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
from faker import Faker
from sqlalchemy import text

from src.config import settings
from src.load.db import session_scope
from src.monitoring.metrics import step


# Fuseau de l'entreprise (Lattes, FR). Sert à dériver start_date_local comme
# le ferait l'API Strava (UTC + heure locale de l'athlète).
PARIS_TZ = ZoneInfo("Europe/Paris")

# Base d'identifiants pour ressembler aux grands id Strava (≈ 10^10).
STRAVA_ID_BASE = 10_000_000_000


# Profil de distribution par sport. Distance/durée échantillonnées par
# log-normale → asymétrique vers le haut, jamais négatif.
@dataclass(frozen=True)
class SportProfile:
    sport_label: str       # nom stocké en DB (sport_type)
    distance_mu: Optional[float]  # log-moyenne (m), None = pas de distance
    distance_sigma: float = 0.4
    duration_mu: float = 7.5      # log-moyenne (s)
    duration_sigma: float = 0.3

    def sample(self, rng: np.random.Generator) -> tuple[Optional[int], int]:
        if self.distance_mu is None:
            dist = None
        else:
            dist = int(rng.lognormal(self.distance_mu, self.distance_sigma))
        dur = int(rng.lognormal(self.duration_mu, self.duration_sigma))
        return dist, dur


# Sports déclarables. Le label DB est explicite (lisible pour l'analyste).
SPORT_PROFILES: dict[str, SportProfile] = {
    "Tennis":         SportProfile("Tennis",         distance_mu=None,           duration_mu=8.2),
    "Course à pied":  SportProfile("Course à pied",  distance_mu=np.log(8000),   duration_mu=8.0),
    "Vélo":           SportProfile("Vélo",           distance_mu=np.log(25000),  duration_mu=8.5),
    "Randonnée":      SportProfile("Randonnée",      distance_mu=np.log(12000),  duration_mu=9.0),
    "Natation":       SportProfile("Natation",       distance_mu=np.log(1500),   duration_mu=7.6),
    "Football":       SportProfile("Football",       distance_mu=None,           duration_mu=8.6),
    "Escalade":       SportProfile("Escalade",       distance_mu=None,           duration_mu=8.7),
    "Yoga":           SportProfile("Yoga",           distance_mu=None,           duration_mu=8.0),
    "Crossfit":       SportProfile("Crossfit",       distance_mu=None,           duration_mu=8.0),
    "Marche":         SportProfile("Marche",         distance_mu=np.log(5000),   duration_mu=8.3),
}


# Mapping libellé FR → sport_type officiel de l'API Strava (anglais).
# Le payload garde le `name` en FR (titre lisible) ET le sport_type Strava.
SPORT_TO_STRAVA: dict[str, str] = {
    "Tennis":         "Tennis",
    "Course à pied":  "Run",
    "Vélo":           "Ride",
    "Randonnée":      "Hike",
    "Natation":       "Swim",
    "Football":       "Soccer",
    "Escalade":       "RockClimbing",
    "Yoga":           "Yoga",
    "Crossfit":       "Crossfit",
    "Marche":         "Walk",
}


# Petits commentaires authentiques distribués au hasard sur ~20 % des activités.
COMMENT_POOL = [
    None, None, None, None,           # 4× plus de NULL que de commentaires
    "Petite séance tranquille",
    "Reprise du sport :)",
    "Super spot à découvrir 🏕",
    "Soleil au rendez-vous",
    "Sortie avec un collègue",
    "PR battu 🎉",
    "Récup entre 2 réunions",
    "Premier essai, j'ai aimé",
]


def _normalize_sport(label: str) -> Optional[str]:
    """La XLSX RH a des libellés variables. On les ramène aux clés de SPORT_PROFILES."""
    if not isinstance(label, str):
        return None
    key = label.strip().lower()
    for canonical in SPORT_PROFILES:
        if canonical.lower() == key:
            return canonical
    # Mapping souple sur les synonymes courants.
    synonyms = {
        "running": "Course à pied",
        "course": "Course à pied",
        "velo": "Vélo",
        "rando": "Randonnée",
        "swim": "Natation",
        "foot": "Football",
    }
    return synonyms.get(key)


def _to_strava_payload(
    activity_id: int,
    emp_id: int,
    sport: str,
    dist_m: Optional[int],
    elapsed_s: int,
    moving_s: int,
    start: datetime,
) -> dict:
    """Construit un enregistrement au format d'une activité de l'API Strava."""
    start_local = start.astimezone(PARIS_TZ)
    return {
        "id": activity_id,
        "athlete": {"id": int(emp_id)},
        "name": sport,                                  # titre lisible (FR)
        "type": SPORT_TO_STRAVA[sport],                 # catégorie (legacy Strava)
        "sport_type": SPORT_TO_STRAVA[sport],           # sport_type Strava (EN)
        "distance": dist_m,                             # mètres (None si non pertinent)
        "moving_time": moving_s,                        # s, temps en mouvement
        "elapsed_time": elapsed_s,                      # s, temps total écoulé
        "start_date": start.isoformat().replace("+00:00", "Z"),
        "start_date_local": start_local.isoformat(),
        "timezone": "(GMT+01:00) Europe/Paris",
        "comment": None,                                # rempli ci-dessous
    }


def generate_payloads() -> list[dict]:
    """Génère la liste des payloads Strava-like sans les insérer (pour tests)."""
    rng = np.random.default_rng(settings.activities_seed)
    Faker.seed(settings.activities_seed)

    with session_scope() as s:
        rows = s.execute(
            text(
                """
                SELECT e.id_employee, sp.sport_pratique
                FROM staging.employees e
                JOIN staging.sports_practice sp USING (id_employee)
                """
            )
        ).all()

    if not rows:
        raise RuntimeError("Aucun (employee, sport) en staging — extract d'abord.")

    # Pré-calcul du nombre d'activités par salarié sur 12 mois.
    by_employee: dict[int, list[str]] = {}
    for emp_id, sport in rows:
        norm = _normalize_sport(sport)
        if norm is None:
            continue
        by_employee.setdefault(emp_id, []).append(norm)

    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    one_year_ago = now - timedelta(days=365)

    employees = list(by_employee.keys())
    total_budget = settings.activities_total
    mean_per_emp = max(5, total_budget // max(1, len(employees)))
    counts = rng.poisson(lam=mean_per_emp, size=len(employees))

    payloads: list[dict] = []
    activity_id = STRAVA_ID_BASE

    for emp_id, n_acts in zip(employees, counts):
        sports = by_employee[emp_id]
        for _ in range(int(n_acts)):
            sport = rng.choice(sports)
            profile = SPORT_PROFILES[sport]
            dist_m, elapsed_s = profile.sample(rng)
            # moving_time = temps écoulé MOINS les pauses → toujours <= elapsed.
            moving_s = int(elapsed_s * rng.uniform(0.85, 0.97))

            # Date de début sur la fenêtre [now-365j, now-1j].
            offset_days = rng.uniform(0, 364)
            start = one_year_ago + timedelta(days=offset_days)
            # Heure : 60 % en matinée 6-10h, 40 % en soirée 17-21h.
            if rng.random() < 0.6:
                start = start.replace(hour=int(rng.uniform(6, 10)),
                                      minute=int(rng.uniform(0, 60)))
            else:
                start = start.replace(hour=int(rng.uniform(17, 21)),
                                      minute=int(rng.uniform(0, 60)))
            # Garde-fou : aucune activité dans le futur (le replace d'heure peut
            # faire dépasser `now` pour les dates proches d'aujourd'hui).
            end = start + timedelta(seconds=elapsed_s)
            if end > now:
                shift = end - now + timedelta(hours=1)
                start -= shift

            activity_id += 1
            payload = _to_strava_payload(
                activity_id, int(emp_id), sport, dist_m, elapsed_s, moving_s, start
            )
            payload["comment"] = rng.choice(COMMENT_POOL)
            payloads.append(payload)

    # Tri chronologique → cohérent pour la lecture humaine et Slack.
    payloads.sort(key=lambda p: p["start_date"])
    return payloads


def load_raw_activities() -> None:
    """Génère les payloads Strava-like et les insère dans raw.activities."""
    with step("generate_activities") as ctx:
        payloads = generate_payloads()
        ctx.rows_in = ctx.rows_out = len(payloads)

    with step("load_raw_activities") as ctx:
        records = [
            {
                "activity_id": p["id"],
                "athlete_id": p["athlete"]["id"],
                "payload": json.dumps(p, ensure_ascii=False),
                "source": "strava_sim",
            }
            for p in payloads
        ]
        with session_scope() as s:
            # CASCADE : staging.activities référence raw.activities (lignage).
            s.execute(text("TRUNCATE raw.activities CASCADE"))
            s.execute(
                text(
                    """
                    INSERT INTO raw.activities
                        (activity_id, athlete_id, payload, source)
                    VALUES
                        (:activity_id, :athlete_id, CAST(:payload AS JSONB), :source)
                    """
                ),
                records,
            )
        ctx.rows_in = ctx.rows_out = len(records)


if __name__ == "__main__":
    load_raw_activities()
    print(f"OK — {settings.activities_total} activités Strava-like générées (cible) "
          f"dans raw.activities avec seed={settings.activities_seed}")
