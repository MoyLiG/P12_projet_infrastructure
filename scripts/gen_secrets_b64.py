"""
Génère les variantes base64 des secrets pour Kestra.

Kestra v0.19 lit les secrets via des variables d'environnement SECRET_* dont
la valeur doit être encodée en base64. Ce script lit les valeurs en clair du
.env et écrit (ou met à jour) les lignes SECRET_*_B64 correspondantes.

Usage :
    python scripts/gen_secrets_b64.py
"""
from __future__ import annotations

import base64
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"

# clair (clé .env) -> nom de la variable base64 attendue par docker-compose
MAPPING = {
    "POSTGRES_PASSWORD": "SECRET_DB_PASSWORD_B64",
    "GOOGLE_MAPS_API_KEY": "SECRET_GOOGLE_MAPS_API_KEY_B64",
    "SLACK_WEBHOOK_URL": "SECRET_SLACK_WEBHOOK_URL_B64",
    "PII_HASH_SALT": "SECRET_PII_HASH_SALT_B64",
}


def main() -> None:
    if not ENV.exists():
        raise SystemExit(".env introuvable — copie .env.example d'abord.")

    lines = ENV.read_text(encoding="utf-8").splitlines()
    values = {}
    for line in lines:
        if "=" in line and not line.strip().startswith("#"):
            k, _, v = line.partition("=")
            values[k.strip()] = v.strip()

    existing = {line.split("=", 1)[0] for line in lines if "=" in line}
    additions = []
    for clear_key, b64_key in MAPPING.items():
        raw = values.get(clear_key, "")
        b64 = base64.b64encode(raw.encode()).decode()
        if b64_key in existing:
            for i, line in enumerate(lines):
                if line.startswith(b64_key + "="):
                    lines[i] = f"{b64_key}={b64}"
        else:
            additions.append(f"{b64_key}={b64}")

    if additions:
        lines.append("")
        lines.append("# --- Secrets base64 pour Kestra (généré) ---")
        lines.extend(additions)

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"OK — {len(MAPPING)} secrets base64 écrits dans {ENV}")


if __name__ == "__main__":
    main()
