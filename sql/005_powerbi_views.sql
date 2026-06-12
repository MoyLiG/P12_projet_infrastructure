-- =====================================================================
-- Vues prêtes pour PowerBI, toutes dans le schéma `marts`.
-- Owned par postgres -> elles agrègent staging/audit en interne, mais
-- powerbi_reader ne lit QUE le résultat (pas d'accès direct aux sources,
-- pas de PII). Colonnes nommées en clair pour un usage BI direct.
-- =====================================================================

\connect sport_data;

-- 1. KPI globaux : une seule ligne, pour les cartes de synthèse.
CREATE OR REPLACE VIEW marts.v_kpi_global AS
SELECT
    (SELECT COUNT(*) FROM marts.employees_safe)                                AS nb_salaries,
    (SELECT COUNT(*) FROM marts.eligibility_prime WHERE is_eligible)           AS nb_eligibles_prime,
    (SELECT COALESCE(SUM(prime_amount),0)
       FROM marts.eligibility_prime WHERE is_eligible)::numeric(12,2)          AS cout_prime_eur,
    (SELECT COUNT(*) FROM marts.eligibility_wellbeing WHERE is_eligible)       AS nb_eligibles_bienetre,
    (SELECT COALESCE(SUM(days_granted),0)
       FROM marts.eligibility_wellbeing WHERE is_eligible)                     AS jours_bienetre,
    (SELECT COUNT(*) FROM marts.employees_safe WHERE is_declaration_suspect)   AS nb_declarations_suspectes;

-- 2. Activités par type de sport (volumétrie + distance moyenne).
CREATE OR REPLACE VIEW marts.v_activities_by_sport AS
SELECT
    sport_type                                          AS sport,
    COUNT(*)                                            AS nb_activites,
    COUNT(DISTINCT id_employee)                         AS nb_salaries,
    ROUND(AVG(distance_m)::numeric / 1000, 2)           AS distance_moyenne_km
FROM staging.activities
WHERE start_dt >= now() - INTERVAL '365 days'
GROUP BY sport_type
ORDER BY nb_activites DESC;

-- 3. Détail prime : 1 ligne / salarié.
--    `id_salarie` (= ID salarié RH) est l'unique identifiant exposé : un
--    pseudonyme interne, opaque pour un analyste non-RH, mais que le seul
--    service RH peut relier à un nom + IBAN (via la table de correspondance
--    source Données+RH.xlsx) pour verser la prime. Pas de hash redondant ici
--    (minimisation RGPD) ; nom/prénom/salaire exact restent hors BI.
CREATE OR REPLACE VIEW marts.v_prime_detail AS
SELECT
    es.id_employee                AS id_salarie,
    es.bu,
    es.salary_band                AS tranche_salaire,
    es.moyen_deplacement,
    es.distance_domicile_m,
    ep.is_eligible                AS eligible,
    ep.prime_rate                 AS taux,
    ep.prime_amount               AS montant_prime_eur,
    ep.reason                     AS motif
FROM marts.employees_safe es
JOIN marts.eligibility_prime ep ON ep.id_employee = es.id_employee;

-- 4. Détail bien-être : 1 ligne / salarié.
--    Même logique que v_prime_detail : `id_salarie` seul = clé RH ré-identifiable
--    par le seul service habilité (pour l'octroi des jours bien-être).
CREATE OR REPLACE VIEW marts.v_wellbeing_detail AS
SELECT
    es.id_employee                AS id_salarie,
    es.bu,
    ew.activity_count             AS nb_activites,
    ew.threshold                  AS seuil,
    ew.is_eligible                AS eligible,
    ew.days_granted               AS jours_accordes,
    ew.reason                     AS motif
FROM marts.employees_safe es
JOIN marts.eligibility_wellbeing ew ON ew.id_employee = es.id_employee;

-- 5. Santé du pipeline : lecture de l'audit, pour la page monitoring.
CREATE OR REPLACE VIEW marts.v_pipeline_health AS
SELECT
    run_id,
    step_name                     AS etape,
    status                        AS statut,
    rows_in                       AS lignes_entree,
    rows_out                      AS lignes_sortie,
    duration_ms                   AS duree_ms,
    started_at                    AS demarre_a,
    message
FROM audit.run_log
ORDER BY started_at DESC;

-- Droits : lecture pour les rôles BI / analyste.
GRANT SELECT ON
    marts.v_kpi_global,
    marts.v_activities_by_sport,
    marts.v_prime_detail,
    marts.v_wellbeing_detail,
    marts.v_pipeline_health
TO powerbi_reader, analyst_reader;
