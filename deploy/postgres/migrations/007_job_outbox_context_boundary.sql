ALTER TABLE source_processing.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_platform_job_id_fkey;

ALTER TABLE source_processing.document_conversion_requests
    DROP CONSTRAINT IF EXISTS document_conversion_requests_job_id_fkey;

ALTER TABLE source_processing.job_outbox
    ADD COLUMN IF NOT EXISTS relay_owner text,
    ADD COLUMN IF NOT EXISTS relay_lease_expires_at timestamptz;

ALTER TABLE source_processing.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_status_check,
    DROP CONSTRAINT IF EXISTS job_outbox_check,
    DROP CONSTRAINT IF EXISTS job_outbox_state_coherence;

ALTER TABLE source_processing.job_outbox
    ADD CONSTRAINT job_outbox_status_check
        CHECK (status IN ('pending', 'relaying', 'relayed')),
    ADD CONSTRAINT job_outbox_state_coherence CHECK (
        (status = 'pending'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL)
        OR (status = 'relaying'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NOT NULL AND relay_lease_expires_at IS NOT NULL)
        OR (status = 'relayed'
            AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL)
    );

CREATE INDEX IF NOT EXISTS source_processing_job_outbox_relay_claim_idx
    ON source_processing.job_outbox (sequence)
    WHERE status IN ('pending', 'relaying');

ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS source_message_id text,
    ADD COLUMN IF NOT EXISTS source_message_hash char(64);

ALTER TABLE platform.technical_jobs
    DROP CONSTRAINT IF EXISTS technical_jobs_source_message_coherence;
ALTER TABLE platform.technical_jobs
    ADD CONSTRAINT technical_jobs_source_message_coherence CHECK (
        (source_message_id IS NULL AND source_message_hash IS NULL)
        OR (source_message_id IS NOT NULL AND source_message_hash IS NOT NULL)
    );

CREATE UNIQUE INDEX IF NOT EXISTS technical_jobs_source_message_id_idx
    ON platform.technical_jobs (source_message_id)
    WHERE source_message_id IS NOT NULL;
