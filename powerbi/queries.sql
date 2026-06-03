-- =====================================================================
-- Requêtes / vues pour PowerBI. Le rôle powerbi_reader n'accède QU'aux
-- vues du schéma marts (sécurité). Toutes les vues sont déjà créées en
-- base (cf. sql/005_powerbi_views.sql) — dans PowerBI il suffit de
-- sélectionner ces vues, pas besoin de coller du SQL.
-- =====================================================================

-- Vues disponibles pour powerbi_reader (schéma marts) :
--   marts.v_kpi_global          1 ligne — cartes de synthèse
--   marts.kpi_by_bu             agrégat par Business Unit
--   marts.v_activities_by_sport volumétrie + distance moyenne par sport
--   marts.v_prime_detail        détail prime par salarié (sans PII)
--   marts.v_wellbeing_detail    détail bien-être par salarié (sans PII)
--   marts.v_pipeline_health     audit des exécutions (monitoring)

-- Aperçu rapide (à exécuter dans psql, pas nécessaire dans PowerBI) :
SELECT * FROM marts.v_kpi_global;
SELECT * FROM marts.kpi_by_bu ORDER BY total_prime_cost_eur DESC;
SELECT * FROM marts.v_activities_by_sport;
SELECT * FROM marts.v_prime_detail WHERE eligible LIMIT 10;
SELECT * FROM marts.v_wellbeing_detail WHERE eligible LIMIT 10;
SELECT * FROM marts.v_pipeline_health LIMIT 50;

-- Détection d'anomalies (déclarations suspectes) — via la vue safe :
SELECT employee_hash, bu, salary_band, moyen_deplacement, distance_domicile_m
FROM marts.employees_safe
WHERE is_declaration_suspect = TRUE
ORDER BY distance_domicile_m DESC;
