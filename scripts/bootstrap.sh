#!/usr/bin/env bash
# =====================================================================
# Bootstrap : démarre la stack et vérifie qu'elle répond.
# Usage : bash scripts/bootstrap.sh
# =====================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "⚠️  .env absent. Copie depuis .env.example puis remplis les secrets."
  cp .env.example .env
  echo "    cp .env.example .env (fait), édite-le maintenant puis relance."
  exit 1
fi

echo "▶️  docker compose up -d --build"
docker compose up -d --build

echo "⏳ Attente Postgres..."
until docker compose exec -T postgres pg_isready -U postgres -d sport_data > /dev/null 2>&1; do
  sleep 2
done
echo "✅ Postgres prêt"

echo "⏳ Attente Kestra (peut prendre ~30 s)..."
until curl -sf http://localhost:8080/api/v1/flows/search > /dev/null 2>&1; do
  sleep 3
done
echo "✅ Kestra prêt"

echo
echo "🎉 Stack opérationnelle :"
echo "    Postgres   → localhost:5432  (db=sport_data)"
echo "    Kestra UI  → http://localhost:8080"
echo
echo "Prochaine étape : déposer Données+RH.xlsx et Données+Sportive.xlsx dans data/raw/"
echo "puis lancer le flow Kestra (UI ou : "
echo "  curl -X POST http://localhost:8080/api/v1/executions/company.sport_data/sport_advantages_etl)"
