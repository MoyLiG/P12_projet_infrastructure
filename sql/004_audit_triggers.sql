-- =====================================================================
-- Triggers d'audit : tracer toute modification sur les marts d'éligibilité
-- pour conformité RGPD (qui a calculé quoi, quand, sur quel run).
-- =====================================================================

\connect sport_data;

CREATE TABLE IF NOT EXISTS audit.eligibility_changes (
  id              BIGSERIAL PRIMARY KEY,
  changed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  changed_by      TEXT NOT NULL DEFAULT current_user,
  table_name      TEXT NOT NULL,
  operation       TEXT NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
  id_employee     BIGINT,
  old_data        JSONB,
  new_data        JSONB
);

CREATE OR REPLACE FUNCTION audit.log_eligibility_change()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO audit.eligibility_changes (
    table_name, operation, id_employee, old_data, new_data
  ) VALUES (
    TG_TABLE_SCHEMA || '.' || TG_TABLE_NAME,
    TG_OP,
    COALESCE(NEW.id_employee, OLD.id_employee),
    CASE WHEN TG_OP IN ('UPDATE','DELETE') THEN to_jsonb(OLD) ELSE NULL END,
    CASE WHEN TG_OP IN ('INSERT','UPDATE') THEN to_jsonb(NEW) ELSE NULL END
  );
  RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS trg_audit_prime ON marts.eligibility_prime;
CREATE TRIGGER trg_audit_prime
  AFTER INSERT OR UPDATE OR DELETE ON marts.eligibility_prime
  FOR EACH ROW EXECUTE FUNCTION audit.log_eligibility_change();

DROP TRIGGER IF EXISTS trg_audit_wellbeing ON marts.eligibility_wellbeing;
CREATE TRIGGER trg_audit_wellbeing
  AFTER INSERT OR UPDATE OR DELETE ON marts.eligibility_wellbeing
  FOR EACH ROW EXECUTE FUNCTION audit.log_eligibility_change();
