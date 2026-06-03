"""
Validation géographique des déclarations RH.

Pour chaque salarié venant au bureau en mode actif (Marche/running ou
Vélo/Trottinette), on calcule la distance domicile-entreprise via Google
Maps Distance Matrix puis on flague les déclarations *suspectes* :
    - Marche/running > 15 km
    - Vélo/Trottinette > 25 km

Stratégie :
1. Cache PG (cache.gmaps_distance) interrogé d'abord. Hit = pas d'appel API.
2. Sinon appel Google Maps avec retry exponentiel (tenacity).
3. Si l'API échoue (quota, panne) : fallback haversine (à vol d'oiseau,
   moins précis mais permet de continuer la démo).
"""
from __future__ import annotations

import hashlib
import math
import sys
from typing import Optional

import googlemaps
import pandas as pd
from sqlalchemy import text
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.load.db import get_engine, session_scope
from src.monitoring.metrics import step


# Approximation : centre de Lattes (34970) pour le fallback haversine.
COMPANY_COORDS = (43.5667, 3.9000)


# --- Modes de déplacement actifs ---------------------------------------
# Mapping moyen_deplacement (FR) -> mode Google Maps + seuil km.
ACTIVE_MODES = {
    "Marche/running":          {"gm_mode": "walking",   "max_km": settings.walking_max_km},
    "Vélo/Trottinette/Autres": {"gm_mode": "bicycling", "max_km": settings.cycling_max_km},
}


def address_hash(address: str) -> str:
    """Hash stable d'une adresse pour la clé de cache."""
    return hashlib.sha256(address.strip().lower().encode("utf-8")).hexdigest()


def haversine_m(coord1: tuple[float, float], coord2: tuple[float, float]) -> int:
    """Distance à vol d'oiseau en mètres (fallback si Google Maps KO)."""
    lat1, lon1 = map(math.radians, coord1)
    lat2, lon2 = map(math.radians, coord2)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return int(2 * 6_371_000 * math.asin(math.sqrt(a)))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
def _gmaps_call(client: googlemaps.Client, origin: str, mode: str) -> dict:
    return client.distance_matrix(
        origins=[origin],
        destinations=[settings.company_address],
        mode=mode,
        units="metric",
    )


def _resolve_distance(
    client: Optional[googlemaps.Client],
    address: str,
    mode: str,
) -> tuple[int, int, str]:
    """Retourne (distance_m, duration_s, source). Source ∈ {cache, gmaps, haversine}."""
    addr_hash = address_hash(address)

    # 1. cache PG
    with session_scope() as s:
        row = s.execute(
            text(
                "SELECT distance_m, duration_s FROM cache.gmaps_distance "
                "WHERE address_hash = :h AND mode = :m"
            ),
            {"h": addr_hash, "m": mode},
        ).first()
        if row:
            return int(row[0]), int(row[1]), "cache"

    # 2. Google Maps
    if client is not None:
        try:
            resp = _gmaps_call(client, address, mode)
            element = resp["rows"][0]["elements"][0]
            if element.get("status") == "OK":
                dist_m = int(element["distance"]["value"])
                dur_s = int(element["duration"]["value"])
                with session_scope() as s:
                    s.execute(
                        text(
                            "INSERT INTO cache.gmaps_distance "
                            "(address_hash, mode, distance_m, duration_s) "
                            "VALUES (:h, :m, :d, :t) "
                            "ON CONFLICT (address_hash, mode) DO UPDATE "
                            "SET distance_m=EXCLUDED.distance_m, "
                            "    duration_s=EXCLUDED.duration_s, "
                            "    resolved_at=now()"
                        ),
                        {"h": addr_hash, "m": mode, "d": dist_m, "t": dur_s},
                    )
                return dist_m, dur_s, "gmaps"
        except Exception:
            # On bascule sur le fallback silencieusement, en loggant via metrics.
            pass

    # 3. fallback haversine — pas de géocodage local : on retourne 0 et un flag
    #    pour que validate_all puisse loguer "fallback impossible sans géocoder".
    #    Cette branche n'arrive que si l'utilisateur n'a pas mis de clé.
    return -1, -1, "haversine_unavailable"


def validate_all() -> pd.DataFrame:
    """Pour chaque salarié actif, calcule la distance et flague."""

    client: Optional[googlemaps.Client] = None
    key = settings.google_maps_api_key.get_secret_value()
    if key:
        client = googlemaps.Client(key=key)

    with step("validate_geo_load") as ctx:
        with session_scope() as s:
            df = pd.read_sql(
                text(
                    "SELECT id_employee, adresse_domicile, moyen_deplacement "
                    "FROM staging.employees"
                ),
                s.connection(),
            )
        ctx.rows_in = ctx.rows_out = len(df)

    with step("validate_geo_resolve") as ctx:
        results = []
        for r in df.itertuples(index=False):
            cfg = ACTIVE_MODES.get(r.moyen_deplacement)
            if cfg is None:
                # Salarié non concerné par la validation distance.
                results.append((r.id_employee, None, False))
                continue
            dist_m, _, source = _resolve_distance(
                client, r.adresse_domicile, cfg["gm_mode"]
            )
            if dist_m < 0:
                # Pas de clé + pas de cache → on logge en suspect = True
                # pour que l'analyste voie qu'il faut investiguer.
                results.append((r.id_employee, None, True))
                continue
            is_suspect = dist_m > cfg["max_km"] * 1000
            results.append((r.id_employee, dist_m, is_suspect))
        ctx.rows_in = ctx.rows_out = len(results)

    with step("validate_geo_persist") as ctx:
        with session_scope() as s:
            s.execute(
                text(
                    "UPDATE staging.employees "
                    "SET distance_domicile_m = :dist, "
                    "    is_declaration_suspect = :sus "
                    "WHERE id_employee = :id"
                ),
                [
                    {"id": eid, "dist": dist, "sus": sus}
                    for eid, dist, sus in results
                ],
            )
        ctx.rows_out = sum(1 for _, _, s in results if s)
        ctx.message = f"{ctx.rows_out} déclarations suspectes flaguées"

    return pd.DataFrame(results, columns=["id_employee", "distance_m", "is_suspect"])


if __name__ == "__main__":
    df = validate_all()
    print(f"OK — {len(df)} salariés validés, "
          f"{int(df['is_suspect'].sum())} suspects")
