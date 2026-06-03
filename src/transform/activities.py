"""
Aplatissement raw.activities (payload JSON Strava-like) → staging.activities.

C'est l'équivalent d'un connecteur d'ingestion : il lit le contrat JSON de la
source (façon API Strava) et le projette sur le schéma métier imposé par la
note de cadrage (ID ; ID salarié ; Date début ; Type ; Distance ; Date fin ;
Commentaire), enrichi de `moving_time_s` et du lien de lignage
`source_activity_id`.

La projection est faite en SQL ensembliste (opérateurs JSONB) plutôt qu'en
pandas : moins de copies en mémoire, et la transformation vit au plus près de
la donnée. Le jour d'un branchement sur la vraie API Strava, ce mapping reste
valable tel quel — seule l'alimentation de raw.activities change.

Mapping payload API Strava → staging.activities :
    payload.id            → source_activity_id   (lignage)
    payload.athlete.id    → id_employee
    payload.start_date    → start_dt
    start_date + elapsed_time → end_dt
    payload.name          → sport_type           (libellé FR lisible)
    payload.distance      → distance_m           (NULL si non pertinent)
    payload.moving_time   → moving_time_s
    payload.comment       → comment
Champs Strava non repris (kudos, polyline, vitesse…) : volontairement écartés
— principe de minimisation des données (PII / RGPD).
"""
from __future__ import annotations

from sqlalchemy import text

from src.load.db import session_scope
from src.monitoring.metrics import step


FLATTEN_SQL = """
INSERT INTO staging.activities
    (source_activity_id, id_employee, start_dt, end_dt,
     sport_type, distance_m, moving_time_s, comment)
SELECT
    r.activity_id,
    r.athlete_id,
    (r.payload->>'start_date')::timestamptz                                AS start_dt,
    (r.payload->>'start_date')::timestamptz
        + make_interval(secs => (r.payload->>'elapsed_time')::int)         AS end_dt,
    r.payload->>'name'                                                     AS sport_type,
    (r.payload->>'distance')::int                                          AS distance_m,
    (r.payload->>'moving_time')::int                                       AS moving_time_s,
    r.payload->>'comment'                                                  AS comment
FROM raw.activities r
ORDER BY (r.payload->>'start_date')::timestamptz
"""


def flatten_activities() -> int:
    """Vide staging.activities et la reremplit depuis raw.activities. Retourne le nb de lignes."""
    with step("transform_activities") as ctx:
        with session_scope() as s:
            n_raw = s.execute(text("SELECT COUNT(*) FROM raw.activities")).scalar_one()
            if n_raw == 0:
                raise RuntimeError(
                    "raw.activities est vide — lancer generate_activities d'abord."
                )
            # TRUNCATE simple (pas RESTART IDENTITY : etl_writer n'est pas
            # propriétaire de la séquence, et id_activity est un surrogate).
            s.execute(text("TRUNCATE staging.activities"))
            s.execute(text(FLATTEN_SQL))
            n_staging = s.execute(
                text("SELECT COUNT(*) FROM staging.activities")
            ).scalar_one()
        ctx.rows_in = int(n_raw)
        ctx.rows_out = int(n_staging)
        ctx.message = f"{n_staging} activités aplaties raw → staging"
    return int(n_staging)


if __name__ == "__main__":
    n = flatten_activities()
    print(f"OK — {n} activités aplaties depuis raw.activities vers staging.activities")
