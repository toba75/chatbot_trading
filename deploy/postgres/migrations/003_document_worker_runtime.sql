ALTER TABLE source_processing.document_processing_runs
    ADD COLUMN IF NOT EXISTS aggregate_version bigint;
UPDATE source_processing.document_processing_runs
   SET aggregate_version = 0
 WHERE aggregate_version IS NULL;
ALTER TABLE source_processing.document_processing_runs
    ALTER COLUMN aggregate_version SET NOT NULL;

ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS trace_id text;
UPDATE platform.technical_jobs
   SET trace_id = 'TRACE-MIGRATED-' || job_id
 WHERE trace_id IS NULL;
ALTER TABLE platform.technical_jobs
    ALTER COLUMN trace_id SET NOT NULL;
ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS lease_owner text;
ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS lease_expires_at timestamptz;
ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS execution_attempts integer NOT NULL DEFAULT 0;
UPDATE platform.technical_jobs
   SET status = 'pending'
 WHERE status = 'running' AND (lease_owner IS NULL OR lease_expires_at IS NULL);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_constraint
         WHERE conname = 'technical_jobs_lease_coherence'
           AND conrelid = 'platform.technical_jobs'::regclass
    ) THEN
        ALTER TABLE platform.technical_jobs
            ADD CONSTRAINT technical_jobs_lease_coherence CHECK (
                (status = 'running' AND lease_owner IS NOT NULL AND lease_expires_at IS NOT NULL)
                OR (status <> 'running' AND lease_owner IS NULL AND lease_expires_at IS NULL)
            );
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS technical_jobs_claim_order_idx
    ON platform.technical_jobs (priority, sequence)
    WHERE status IN ('pending', 'running');

CREATE TABLE IF NOT EXISTS source_processing.job_outbox (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    outbox_id text GENERATED ALWAYS AS (
        'OUTBOX-SP-' || lpad(sequence::text, 10, '0')
    ) STORED UNIQUE,
    job_name text NOT NULL,
    priority text NOT NULL CHECK (priority IN ('P0', 'P1', 'P2', 'P3', 'P4', 'P5')),
    input_hash char(64) NOT NULL,
    configuration_hash char(64) NOT NULL,
    code_version text NOT NULL,
    model_version text NOT NULL,
    payload jsonb NOT NULL,
    trace_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'relayed')),
    relay_attempts integer NOT NULL DEFAULT 0 CHECK (relay_attempts >= 0),
    platform_job_id text UNIQUE REFERENCES platform.technical_jobs(job_id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    relayed_at timestamptz,
    CHECK (
        (status = 'pending' AND platform_job_id IS NULL AND relayed_at IS NULL)
        OR (status = 'relayed' AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL)
    ),
    UNIQUE (job_name, input_hash, configuration_hash, code_version, model_version)
);

CREATE INDEX IF NOT EXISTS source_processing_job_outbox_pending_idx
    ON source_processing.job_outbox (sequence)
    WHERE status = 'pending';

ALTER TABLE source_processing.document_conversion_requests
    ADD COLUMN IF NOT EXISTS submission_id text;
UPDATE source_processing.document_conversion_requests
   SET submission_id = job_id
 WHERE submission_id IS NULL;
ALTER TABLE source_processing.document_conversion_requests
    ALTER COLUMN submission_id SET NOT NULL;
ALTER TABLE source_processing.document_conversion_requests
    ALTER COLUMN job_id DROP NOT NULL;
