#!/usr/bin/env bash
# =====================================================================
# Script de démo soutenance.
# Joue les deux scénarios exigés par OC :
#   a) Modifier le taux de prime (5 % → 7 %), relancer, voir le delta
#   b) Insérer une nouvelle activité, voir le message Slack arriver
#
# Usage :
#   bash scripts/demo.sh        # joue les deux scénarios (a puis b)
#   bash scripts/demo.sh a      # joue UNIQUEMENT le scénario A
#   bash scripts/demo.sh b      # joue UNIQUEMENT le scénario B
#
# À lancer depuis la RACINE du projet (le module Python a besoin de voir
# le dossier src/ dans le répertoire courant).
# =====================================================================
set -euo pipefail

KESTRA="http://localhost:8080"
FLOW="company.sport_data/sport_advantages_etl"
PG="docker compose exec -T postgres psql -U postgres -d sport_data"

# Python du venv (Windows ou Linux) sinon python du PATH. Le scénario B lance
# un module Python sur le host : le .env pointe localhost:5432 + le vrai webhook.
if [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
else
  PY="python"
fi

# --- Helpers ---------------------------------------------------------

# Parsing JSON FIABLE. Un grep/head naïf ne marche pas : le JSON d'exécution
# Kestra répète la clé "current" (une par tâche + une pour l'exécution) ->
# head -1 attrape l'état de la 1re tâche, pas celui du run. Il faut naviguer la
# structure -> jq si présent, sinon python3 (présent par défaut sur Ubuntu/WSL).
if command -v jq >/dev/null 2>&1; then
  JSON_TOOL="jq"
elif command -v python3 >/dev/null 2>&1; then
  JSON_TOOL="py"
else
  echo "❌ Il faut 'jq' OU 'python3' pour parser l'API Kestra." >&2
  echo "   Installe l'un des deux, ex. : sudo apt install -y jq" >&2
  exit 1
fi

# Lit l'id d'exécution depuis la réponse POST (stdin).
get_id() {
  if [ "$JSON_TOOL" = "jq" ]; then
    jq -r '.id'
  else
    python3 -c 'import sys,json;print(json.load(sys.stdin)["id"])'
  fi
}

# Lit l'état GLOBAL de l'exécution (.state.current) depuis le GET (stdin).
get_state() {
  if [ "$JSON_TOOL" = "jq" ]; then
    jq -r '.state.current'
  else
    python3 -c 'import sys,json;print(json.load(sys.stdin)["state"]["current"])'
  fi
}

# Déclenche le flow avec un taux de prime donné. Les logs partent sur stderr ;
# seul l'id d'exécution sort sur stdout (capturable via $(trigger ...)).
trigger() {
  local rate=$1
  echo >&2
  echo "▶️  Run flow avec prime_rate=$rate" >&2
  # L'API Kestra exige du multipart/form-data (-F). En urlencoded (-d) elle
  # répond 415/422 -> avec set -e + pipefail le script s'arrêtait sans rien dire.
  curl -sf -X POST "$KESTRA/api/v1/executions/$FLOW" \
    -F "prime_rate=$rate" \
    -F "wellbeing_threshold=15" | get_id
}

# Attend la fin réelle d'une exécution Kestra (poll de l'API jusqu'à un état
# terminal) au lieu d'un sleep fixe : on lit les KPI seulement quand le run
# est vraiment fini. Timeout de sécurité (défaut 180 s).
wait_execution() {
  local id=$1
  local timeout=${2:-180}
  local waited=0
  local state
  echo "⏳ Attente fin du run $id..." >&2
  while true; do
    state=$(curl -sf "$KESTRA/api/v1/executions/$id" | get_state)
    case "$state" in
      SUCCESS|WARNING)
        echo "   ✅ état final : $state (${waited}s)" >&2
        return 0 ;;
      FAILED|KILLED)
        echo "   ❌ état final : $state — voir l'UI Kestra et audit.run_log" >&2
        return 1 ;;
    esac
    if [ "$waited" -ge "$timeout" ]; then
      echo "   ⏱️  timeout après ${timeout}s (dernier état : $state)" >&2
      return 1
    fi
    sleep 2
    waited=$((waited + 2))
  done
}

show_kpi() {
  $PG -c "SELECT prime_rate, COUNT(*) FILTER (WHERE is_eligible) AS nb_eligible,
                 SUM(prime_amount)::numeric(12,2) AS cout_total
          FROM marts.eligibility_prime
          GROUP BY prime_rate ORDER BY prime_rate;"
}

# --- Scénarios -------------------------------------------------------

scenario_a() {
  echo "=========================================================="
  echo "  Scénario A — modifier le taux de prime"
  echo "=========================================================="
  local id
  id=$(trigger 0.05)
  wait_execution "$id"
  show_kpi

  id=$(trigger 0.07)
  wait_execution "$id"
  show_kpi
}

scenario_b() {
  echo "=========================================================="
  echo "  Scénario B — insérer une nouvelle activité en live"
  echo "=========================================================="
  # On insère directement dans staging.activities pour simuler l'arrivée d'une
  # nouvelle activité (en prod : webhook Strava -> raw -> flatten incrémental).
  # IMPORTANT : ne PAS relancer le flow complet ici. transform_activities fait un
  # TRUNCATE de staging.activities avant de recharger depuis raw -> l'insert
  # serait effacé avant d'atteindre l'étape Slack. On joue donc UNIQUEMENT la
  # notification.
  $PG -c "INSERT INTO staging.activities
              (id_employee, start_dt, end_dt, sport_type, distance_m, moving_time_s, comment, posted_to_slack)
          VALUES ((SELECT id_employee FROM staging.employees ORDER BY random() LIMIT 1),
                  now() - interval '45 minutes',
                  now(),
                  'Course à pied',
                  8200,
                  2700,
                  'Run de démo soutenance 🎤',
                  FALSE);"

  echo "▶️  Notification Slack de la seule nouvelle activité (--limit 1)"
  # --limit 1 : start_dt = now() => la nouvelle activité est la plus récente,
  # donc la seule postée. Idempotent : posted_to_slack passe à TRUE (pas de
  # doublon si on rejoue).
  "$PY" -m src.load.slack --limit 1

  echo "✅ Démo terminée — un message doit être arrivé dans #tous-sport-data-solution."
}

# --- Dispatcher ------------------------------------------------------
# ${1:-all} : prend le 1er argument, ou "all" si absent (rétro-compatible).
case "${1:-all}" in
  a)   scenario_a ;;
  b)   scenario_b ;;
  all) scenario_a; scenario_b ;;
  *)   echo "Usage: $0 [a|b]   (sans argument = les deux scénarios)"; exit 1 ;;
esac
