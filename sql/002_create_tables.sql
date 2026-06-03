-- =====================================================================
-- Tables du POC. Contraintes CHECK = première ligne de défense qualité,
-- AVANT même Great Expectations.
-- =====================================================================

\connect sport_data;

-- ---------------------------------------------------------------------
-- raw : reflet des XLSX source. Noms de colonnes francisés tels quels.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS raw.employees_xlsx (
  loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_file      TEXT NOT NULL,
  id_salarie       BIGINT,
  nom              TEXT,
  prenom           TEXT,
  date_naissance   DATE,
  bu               TEXT,
  date_embauche    DATE,
  salaire_brut     NUMERIC(12,2),
  type_contrat     TEXT,
  jours_cp         INT,
  adresse_domicile TEXT,
  moyen_deplacement TEXT
);

CREATE TABLE IF NOT EXISTS raw.sports_xlsx (
  loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  source_file      TEXT NOT NULL,
  id_salarie       BIGINT,
  sport_pratique   TEXT
);

-- ---------------------------------------------------------------------
-- staging : typage strict + contraintes métier basiques.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS staging.employees (
  id_employee       BIGINT PRIMARY KEY,
  -- PII en clair (visible pour rôle etl_writer / dba uniquement) :
  nom               TEXT NOT NULL,
  prenom            TEXT NOT NULL,
  -- Hash pseudonyme pour le rôle analyst_reader (RLS plus loin).
  nom_hash          TEXT NOT NULL,
  date_naissance    DATE NOT NULL,
  bu                TEXT NOT NULL,
  date_embauche     DATE NOT NULL,
  salaire_brut      NUMERIC(12,2) NOT NULL CHECK (salaire_brut > 0),
  type_contrat      TEXT NOT NULL,
  jours_cp          INT NOT NULL CHECK (jours_cp >= 0),
  adresse_domicile  TEXT NOT NULL,
  -- Enum aligné sur les 4 modalités réelles du fichier RH (cf. note de cadrage).
  moyen_deplacement TEXT NOT NULL CHECK (
    moyen_deplacement IN (
      'Marche/running',
      'Vélo/Trottinette/Autres',
      'Transports en commun',
      'véhicule thermique/électrique'
    )
  ),
  -- Renseigné par validate/geo.py
  distance_domicile_m INT CHECK (distance_domicile_m >= 0),
  is_declaration_suspect BOOLEAN DEFAULT FALSE,
  loaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS staging.sports_practice (
  id_employee     BIGINT REFERENCES staging.employees(id_employee),
  sport_pratique  TEXT,
  loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (id_employee, sport_pratique)
);

CREATE TABLE IF NOT EXISTS staging.activities (
  id_activity     BIGSERIAL PRIMARY KEY,
  id_employee     BIGINT NOT NULL REFERENCES staging.employees(id_employee),
  start_dt        TIMESTAMPTZ NOT NULL,
  end_dt          TIMESTAMPTZ NOT NULL,
  sport_type      TEXT NOT NULL,
  distance_m      INT,                    -- NULL autorisé (ex. escalade)
  comment         TEXT,
  posted_to_slack BOOLEAN NOT NULL DEFAULT FALSE,
  loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_dt > start_dt),
  CHECK (distance_m IS NULL OR distance_m >= 0)
);

CREATE INDEX IF NOT EXISTS idx_activities_employee ON staging.activities(id_employee);
CREATE INDEX IF NOT EXISTS idx_activities_start_dt ON staging.activities(start_dt);

-- ---------------------------------------------------------------------
-- marts : output pour PowerBI.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS marts.eligibility_prime (
  id_employee   BIGINT PRIMARY KEY REFERENCES staging.employees(id_employee),
  is_eligible   BOOLEAN NOT NULL,
  prime_rate    NUMERIC(5,4) NOT NULL,           -- ex 0.0500 = 5 %
  prime_amount  NUMERIC(12,2) NOT NULL CHECK (prime_amount >= 0),
  reason        TEXT NOT NULL,
  computed_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_id        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS marts.eligibility_wellbeing (
  id_employee     BIGINT PRIMARY KEY REFERENCES staging.employees(id_employee),
  is_eligible     BOOLEAN NOT NULL,
  activity_count  INT NOT NULL CHECK (activity_count >= 0),
  threshold       INT NOT NULL,
  days_granted    INT NOT NULL CHECK (days_granted >= 0),
  reason          TEXT NOT NULL,
  computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  run_id          TEXT NOT NULL
);

-- Vue agrégée par BU pour le dashboard PowerBI.
CREATE OR REPLACE VIEW marts.kpi_by_bu AS
SELECT
    e.bu,
    COUNT(DISTINCT e.id_employee)                                   AS nb_employees,
    COUNT(DISTINCT e.id_employee) FILTER (WHERE p.is_eligible)      AS nb_eligible_prime,
    COUNT(DISTINCT e.id_employee) FILTER (WHERE w.is_eligible)      AS nb_eligible_wellbeing,
    COALESCE(SUM(p.prime_amount) FILTER (WHERE p.is_eligible), 0)   AS total_prime_cost_eur,
    COALESCE(SUM(w.days_granted) FILTER (WHERE w.is_eligible), 0)   AS total_wellbeing_days
FROM staging.employees e
LEFT JOIN marts.eligibility_prime p USING (id_employee)
LEFT JOIN marts.eligibility_wellbeing w USING (id_employee)
GROUP BY e.bu;

-- ---------------------------------------------------------------------
-- audit : monitoring du pipeline.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit.run_log (
  id            BIGSERIAL PRIMARY KEY,
  run_id        TEXT NOT NULL,
  step_name     TEXT NOT NULL,
  status        TEXT NOT NULL CHECK (status IN ('OK','WARN','FAIL')),
  rows_in       INT,
  rows_out      INT,
  duration_ms   INT,
  message       TEXT,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_run_log_run_id ON audit.run_log(run_id);

-- ---------------------------------------------------------------------
-- cache Google Maps.
-- ---------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cache.gmaps_distance (
  address_hash    TEXT NOT NULL,
  mode            TEXT NOT NULL CHECK (mode IN ('walking','bicycling','driving','transit')),
  distance_m      INT NOT NULL,
  duration_s      INT NOT NULL,
  resolved_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (address_hash, mode)
);
