-- =====================================================================
-- Rôles et permissions. Trois rôles applicatifs + le superuser.
-- Principe : least privilege — analyst_reader ne voit JAMAIS les PII.
-- =====================================================================

\connect sport_data;

-- ---------------------------------------------------------------------
-- 1. etl_writer — utilisé par les scripts Python du pipeline.
--    Peut lire/écrire raw, staging, marts, audit, cache.
-- ---------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_writer') THEN
    CREATE ROLE etl_writer LOGIN PASSWORD 'change-me-please-strong-pwd';
  END IF;
END$$;

GRANT USAGE  ON SCHEMA raw, staging, marts, audit, cache TO etl_writer;
-- TRUNCATE est un privilège distinct de DELETE en PostgreSQL : le pipeline
-- l'utilise pour vider les tables avant rechargement (RESTART IDENTITY).
GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE
  ON ALL TABLES IN SCHEMA raw, staging, marts, audit, cache TO etl_writer;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA staging, marts, audit TO etl_writer;
-- Les futurs objets créés héritent automatiquement des mêmes droits.
ALTER DEFAULT PRIVILEGES IN SCHEMA raw, staging, marts, audit, cache
  GRANT SELECT, INSERT, UPDATE, DELETE, TRUNCATE ON TABLES TO etl_writer;

-- ---------------------------------------------------------------------
-- 2. analyst_reader — utilisé par PowerBI / analystes.
--    Lecture marts uniquement. ZERO accès aux PII de staging.employees.
-- ---------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_reader') THEN
    CREATE ROLE analyst_reader LOGIN PASSWORD 'change-me-analyst-pwd';
  END IF;
END$$;

GRANT USAGE ON SCHEMA marts TO analyst_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO analyst_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts
  GRANT SELECT ON TABLES TO analyst_reader;

-- Vue "safe" pour les analystes : NOMS HASHÉS, salaires masqués par tranche.
CREATE OR REPLACE VIEW marts.employees_safe AS
SELECT
    id_employee,
    nom_hash                              AS employee_hash,
    bu,
    CASE
      WHEN salaire_brut < 30000 THEN '< 30k'
      WHEN salaire_brut < 50000 THEN '30-50k'
      WHEN salaire_brut < 80000 THEN '50-80k'
      ELSE '> 80k'
    END                                   AS salary_band,
    moyen_deplacement,
    distance_domicile_m,
    is_declaration_suspect
FROM staging.employees;

-- L'analyst peut lire la vue safe mais pas la table source.
GRANT SELECT ON marts.employees_safe TO analyst_reader;

-- ---------------------------------------------------------------------
-- 3. powerbi_reader — alias pour clarté (peut être confondu avec analyst).
--    Strictement équivalent à analyst_reader pour ce POC.
-- ---------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'powerbi_reader') THEN
    CREATE ROLE powerbi_reader LOGIN PASSWORD 'change-me-pbi-pwd';
  END IF;
END$$;

GRANT USAGE ON SCHEMA marts TO powerbi_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA marts TO powerbi_reader;
GRANT SELECT ON marts.employees_safe TO powerbi_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA marts
  GRANT SELECT ON TABLES TO powerbi_reader;

-- ---------------------------------------------------------------------
-- Row Level Security : interdire explicitement la lecture brute de
-- staging.employees aux rôles non habilités. Belt-and-suspenders.
-- ---------------------------------------------------------------------
ALTER TABLE staging.employees ENABLE ROW LEVEL SECURITY;

CREATE POLICY employees_etl_full ON staging.employees
  FOR ALL TO etl_writer
  USING (true) WITH CHECK (true);

-- Les autres rôles ne sont volontairement pas dans la policy → 0 ligne lue.
