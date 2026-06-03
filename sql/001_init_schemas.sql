-- =====================================================================
-- Sport Data Solution — Init des schémas
-- Pattern dbt-like : raw / staging / marts + audit + cache
-- Exécuté automatiquement au premier démarrage du conteneur postgres
-- (volume /docker-entrypoint-initdb.d).
-- =====================================================================

\connect sport_data;

-- Données brutes : copie 1:1 de la source, jamais modifiée (audit trail).
CREATE SCHEMA IF NOT EXISTS raw;

-- Données typées et nettoyées, prêtes pour les calculs métier.
CREATE SCHEMA IF NOT EXISTS staging;

-- Tables finales consommées par PowerBI (eligibility, KPI agrégés).
CREATE SCHEMA IF NOT EXISTS marts;

-- Logs d'exécution du pipeline (volumétrie, durée, statut par étape).
CREATE SCHEMA IF NOT EXISTS audit;

-- Cache des appels Google Maps Distance Matrix (évite de re-payer).
CREATE SCHEMA IF NOT EXISTS cache;

COMMENT ON SCHEMA raw IS 'Données brutes (copie 1:1 source) — JAMAIS modifiées';
COMMENT ON SCHEMA staging IS 'Données typées/nettoyées — input des calculs métier';
COMMENT ON SCHEMA marts IS 'Tables finales pour PowerBI (eligibility, KPI)';
COMMENT ON SCHEMA audit IS 'Logs pipeline : volumétrie, durée, statut par run';
COMMENT ON SCHEMA cache IS 'Cache distance Google Maps (idempotence + coût)';
