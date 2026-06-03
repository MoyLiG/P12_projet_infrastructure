"""
Générateur d'activités sportives (Strava-like).

Spec :
- Crée ~settings.activities_total lignes sur les 12 derniers mois.
- Chaque salarié ayant une `sport_pratique` reçoit un nombre d'activités
  tiré d'une loi de Poisson centrée sur 25/an → distribution réaliste
  (certains salariés autour de 5, d'autres autour de 50).
- Le `sport_type` de chaque activité reste cohérent avec ce qu'il pratique.
- Distance et durée tirées de distributions par sport (cf. SPORT_PROFILES).
- Seed fixe (settings.activities_seed) → reproductibilité totale.

Pourquoi un générateur "intelligent" plutôt que random pur ?
→ Évite l'incohérence ("salarié escaladeur qui fait 12 km de course") qui
  rendrait le POC ridicule en soutenance.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
import pandas as pd
from faker import Faker
from sqlalchemy import text

from src.config import settings
from src.load.db import get_engine, session_scope
from src.monitoring.metrics import step


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


def generate_activities() -> pd.DataFrame:
    """Génère le DataFrame d'activités sans l'insérer (pour tests)."""
    rng = np.random.default_rng(settings.activities_seed)
    fk = Faker("fr_FR")
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
    # Poisson(mean=25) → la majorité entre 15 et 35.
    by_employee: dict[int, list[str]] = {}
    for emp_id, sport in rows:
        norm = _normalize_sport(sport)
        if norm is None:
            continue
        by_employee.setdefault(emp_id, []).append(norm)

    now = datetime.now(tz=timezone.utc).replace(microsecond=0)
    one_year_ago = now - timedelta(days=365)

    records: list[dict] = []
    total_budget = settings.activities_total

    # Stratégie : on tire un budget global, puis on le distribue
    # proportionnellement aux salariés (Poisson autour de moyenne calibrée).
    employees = list(by_employee.keys())
    mean_per_emp = max(5, total_budget // max(1, len(employees)))
    counts = rng.poisson(lam=mean_per_emp, size=len(employees))

    for emp_id, n_acts in zip(employees, counts):
        sports = by_employee[emp_id]
        for _ in range(int(n_acts)):
            sport = rng.choice(sports)
            profile = SPORT_PROFILES[sport]
            dist_m, dur_s = profile.sample(rng)

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
            end = start + timedelta(seconds=dur_s)
            # Garde-fou : aucune activité dans le futur (le replace d'heure
            # peut faire dépasser `now` pour les dates proches d'aujourd'hui).
            if end > now:
                shift = end - now + timedelta(hours=1)
                start -= shift
                end -= shift

            records.append(
                {
                    "id_employee": int(emp_id),
                    "start_dt": start,
                    "end_dt": end,
                    "sport_type": profile.sport_label,
                    "distance_m": dist_m,
                    "comment": rng.choice(COMMENT_POOL),
                }
            )

    df = pd.DataFrame(records)
    # Tri chronologique → cohérent pour la lecture humaine et Slack.
    df = df.sort_values("start_dt").reset_index(drop=True)
    return df


def load_activities() -> None:
    with step("generate_activities") as ctx:
        df = generate_activities()
        ctx.rows_in = ctx.rows_out = len(df)

    with step("load_activities") as ctx:
        # pandas met NaN (float) pour les distances absentes (Escalade, Tennis…).
        # La colonne SQL est INT → il faut convertir NaN en None (= SQL NULL).
        records = df.to_dict(orient="records")
        for r in records:
            if pd.isna(r["distance_m"]):
                r["distance_m"] = None
            else:
                r["distance_m"] = int(r["distance_m"])
        with session_scope() as s:
            s.execute(text("TRUNCATE staging.activities CASCADE"))
            s.execute(
                text(
                    """
                    INSERT INTO staging.activities
                        (id_employee, start_dt, end_dt, sport_type, distance_m, comment)
                    VALUES
                        (:id_employee, :start_dt, :end_dt, :sport_type, :distance_m, :comment)
                    """
                ),
                records,
            )
        ctx.rows_in = ctx.rows_out = len(records)


if __name__ == "__main__":
    load_activities()
    print(f"OK — {settings.activities_total} activités générées (cible) "
          f"avec seed={settings.activities_seed}")
