#!/usr/bin/env bash
# =====================================================================
# Script de démo soutenance.
# Joue les deux scénarios exigés par OC :
#   a) Modifier le taux de prime (5 % → 7 %), relancer, voir le delta
#   b) Insérer une nouvelle activité, voir le message Slack arriver
# =====================================================================
set -euo pipefail

KESTRA="http://localhost:8080"
FLOW="company.sport_data/sport_advantages_etl"
PG="docker compose exec -T postgres psql -U postgres -d sport_data"

trigger() {
  local rate=$1
  echo
  echo "▶️  Run flow avec prime_rate=$rate"
  curl -sf -X POST "$KESTRA/api/v1/executions/$FLOW" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "prime_rate=$rate&wellbeing_threshold=15" | jq -r .id
}

show_kpi() {
  $PG -c "SELECT prime_rate, COUNT(*) FILTER (WHERE is_eligible) AS nb_eligible,
                 SUM(prime_amount)::numeric(12,2) AS cout_total
          FROM marts.eligibility_prime
          GROUP BY prime_rate ORDER BY prime_rate;"
}

echo "=========================================================="
echo "  Scénario A — modifier le taux de prime"
echo "=========================================================="
trigger 0.05
echo "⏳ Attente fin du run..."
sleep 30
show_kpi

trigger 0.07
sleep 30
show_kpi

echo "=========================================================="
echo "  Scénario B — insérer une nouvelle activité en live"
echo "=========================================================="
$PG -c "INSERT INTO staging.activities (id_employee, start_dt, end_dt, sport_type, distance_m, comment)
        VALUES ((SELECT id_employee FROM staging.employees LIMIT 1),
                now() - interval '5 minutes',
                now(),
                'Course à pied',
                10800,
                'Course de démo en soutenance 🎤');"

echo "▶️  Run de notification Slack uniquement"
$PG -c "UPDATE staging.activities SET posted_to_slack = FALSE
        WHERE start_dt > now() - interval '10 minutes';"
docker compose exec -T kestra curl -sf -X POST "$KESTRA/api/v1/executions/$FLOW"

echo "✅ Démo prête — vérifie Slack et PowerBI."
