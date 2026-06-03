"""
Notifications Slack — Incoming Webhook.

Pour chaque nouvelle activité non encore postée, on envoie un message dans
`#sport-data`. Le flag `posted_to_slack` en DB garantit l'idempotence : si
le pipeline est rejoué, on ne spamme pas la channel.

Mode dégradé : si le webhook répond 4xx/5xx, on écrit le message dans
`data/generated/slack_outbox.jsonl` et on continue. Le pipeline ne casse pas.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import requests
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.load.db import session_scope
from src.monitoring.metrics import step


OUTBOX = Path("data/generated/slack_outbox.jsonl")

# Phrases d'encouragement. La variété évite l'aspect "bot mort" en démo.
TEMPLATES = [
    "Bravo {prenom} {nom} ! Tu viens de faire {sport_lower} sur {distance} en {duree} ! Quelle énergie ! 🔥🏅",
    "Magnifique {prenom} {nom} ! Une session de {sport_lower} de {distance} terminée en {duree} ! 🌄",
    "Allez {prenom} {nom} ! Encore une activité {sport_lower} de {distance} bouclée en {duree} 💪",
    "{prenom} {nom} est en feu ! {sport_lower} : {distance} en {duree} 🚴‍♂️",
]


def _format_distance(distance_m) -> str:
    if distance_m is None:
        return "session"
    return f"{distance_m / 1000:.1f} km"


def _format_duration(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    if minutes >= 60:
        h, m = divmod(minutes, 60)
        return f"{h} h {m:02d}"
    return f"{minutes} min"


def _build_text(row: dict) -> str:
    template = random.choice(TEMPLATES)
    msg = template.format(
        prenom=row["prenom"],
        nom=row["nom"],
        sport_lower=row["sport_type"].lower(),
        distance=_format_distance(row["distance_m"]),
        duree=_format_duration(
            int((row["end_dt"] - row["start_dt"]).total_seconds())
        ),
    )
    if row.get("comment"):
        msg += f' ("{row["comment"]}")'
    return msg


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
def _post_webhook(url: str, payload: dict) -> int:
    r = requests.post(url, json=payload, timeout=10)
    if r.status_code >= 400:
        raise RuntimeError(f"Webhook {r.status_code}: {r.text}")
    return r.status_code


def post_new_activities(limit: int = 50) -> int:
    """Récupère les activités non postées (les plus récentes d'abord), poste, marque."""

    webhook = settings.slack_webhook_url.get_secret_value()
    OUTBOX.parent.mkdir(parents=True, exist_ok=True)

    with step("slack_fetch_pending") as ctx:
        with session_scope() as s:
            rows = s.execute(
                text(
                    """
                    SELECT a.id_activity, a.id_employee, a.start_dt, a.end_dt,
                           a.sport_type, a.distance_m, a.comment,
                           e.nom, e.prenom
                    FROM staging.activities a
                    JOIN staging.employees e USING (id_employee)
                    WHERE a.posted_to_slack = FALSE
                    ORDER BY a.start_dt DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            ).mappings().all()
        ctx.rows_in = ctx.rows_out = len(rows)

    if not rows:
        return 0

    posted_ids = []
    with step("slack_post") as ctx:
        for row in rows:
            text_msg = _build_text(dict(row))
            payload = {"text": text_msg, "channel": settings.slack_channel}
            try:
                if webhook:
                    _post_webhook(webhook, payload)
                else:
                    raise RuntimeError("Pas de webhook configuré")
            except Exception as e:
                # fallback : log en jsonl, on continue (pipeline ne casse pas)
                with OUTBOX.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(
                        {"payload": payload, "error": str(e)},
                        ensure_ascii=False, default=str,
                    ) + "\n")
            posted_ids.append(row["id_activity"])
        ctx.rows_out = len(posted_ids)
        ctx.message = f"{len(posted_ids)} messages postés / fallback log"

    with step("slack_mark_posted") as ctx:
        with session_scope() as s:
            s.execute(
                text(
                    "UPDATE staging.activities SET posted_to_slack = TRUE "
                    "WHERE id_activity = ANY(:ids)"
                ),
                {"ids": posted_ids},
            )
        ctx.rows_out = len(posted_ids)

    return len(posted_ids)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, default=50,
        help="Nombre max de messages postés par run (anti-flood).",
    )
    args = parser.parse_args()
    n = post_new_activities(limit=args.limit)
    print(f"OK — {n} activités postées (ou fallback log)")
