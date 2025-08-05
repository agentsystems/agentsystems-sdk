-- Idempotent creation of required objects for Agent Control Plane audit logging

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_token TEXT NOT NULL,
    thread_id UUID NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT NOT NULL,
    status_code SMALLINT NOT NULL,
    payload JSONB,
    error_msg TEXT
);

-- ── Hash-chaining for tamper-evident ledger ───────────────────────────────
-- Add columns if they do not yet exist
ALTER TABLE audit_log
  ADD COLUMN IF NOT EXISTS prev_hash TEXT,
  ADD COLUMN IF NOT EXISTS entry_hash TEXT;

-- Genesis hash table (single-row)
CREATE TABLE IF NOT EXISTS audit_meta(
  genesis_hash TEXT PRIMARY KEY
);
INSERT INTO audit_meta(genesis_hash)
  VALUES ('00000000000000000000000000000000')
  ON CONFLICT DO NOTHING;

-- Trigger function: compute chained hash before insert
CREATE OR REPLACE FUNCTION audit_chain() RETURNS TRIGGER AS $$
DECLARE
    last_hash TEXT;
BEGIN
    -- First try to get the last entry's hash
    SELECT entry_hash INTO last_hash
    FROM audit_log
    ORDER BY timestamp DESC
    LIMIT 1;

    -- If no entries exist, use genesis hash
    IF last_hash IS NULL THEN
        SELECT genesis_hash INTO last_hash FROM audit_meta;
    END IF;

    NEW.prev_hash := last_hash;
    NEW.entry_hash := encode(digest(NEW.prev_hash || row_to_json(NEW)::TEXT, 'sha256'),'hex');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Ensure one trigger attached
DROP TRIGGER IF EXISTS trg_audit_chain ON audit_log;
CREATE TRIGGER trg_audit_chain
BEFORE INSERT ON audit_log
FOR EACH ROW
EXECUTE FUNCTION audit_chain();
