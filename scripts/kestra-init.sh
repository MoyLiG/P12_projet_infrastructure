#!/bin/sh
# Importe (ou met à jour) le flow Kestra dès que l'API répond.
# Monté dans le conteneur kestra-init.
set -e

echo "Attente de l'API Kestra..."
until curl -sf http://kestra:8080/api/v1/flows/search > /dev/null 2>&1; do
  echo "  ...Kestra pas encore prêt"
  sleep 3
done

echo "Import du flow sport_advantages_etl..."
# POST crée le flow ; si déjà présent (409), on bascule sur PUT (update).
if curl -sf -X POST \
      -H "Content-Type: application/x-yaml" \
      --data-binary @/flows/sport_advantages_etl.yaml \
      http://kestra:8080/api/v1/flows > /dev/null 2>&1; then
  echo "Flow créé."
else
  echo "Flow déjà existant -> mise à jour (PUT)."
  curl -sf -X PUT \
      -H "Content-Type: application/x-yaml" \
      --data-binary @/flows/sport_advantages_etl.yaml \
      http://kestra:8080/api/v1/flows/company.sport_data/sport_advantages_etl \
      > /dev/null 2>&1 && echo "Flow mis à jour." || echo "Échec de l'import."
fi
