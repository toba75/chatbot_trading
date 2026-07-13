ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS claim_generation bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS claim_token uuid;

UPDATE platform.technical_jobs
   SET claim_generation = GREATEST(execution_attempts, 1),
       claim_token = gen_random_uuid()
 WHERE status = 'running'
   AND (claim_generation = 0 OR claim_token IS NULL);

ALTER TABLE platform.technical_jobs
    DROP CONSTRAINT IF EXISTS technical_jobs_lease_coherence;
ALTER TABLE platform.technical_jobs
    ADD CONSTRAINT technical_jobs_lease_coherence CHECK (
        (status = 'running'
            AND lease_owner IS NOT NULL
            AND lease_expires_at IS NOT NULL
            AND claim_generation > 0
            AND claim_generation = execution_attempts
            AND claim_token IS NOT NULL)
        OR (status <> 'running'
            AND lease_owner IS NULL
            AND lease_expires_at IS NULL
            AND claim_token IS NULL)
    );

DROP INDEX IF EXISTS platform.technical_jobs_claim_order_idx;
CREATE INDEX IF NOT EXISTS technical_jobs_pending_claim_idx
    ON platform.technical_jobs (job_name, priority, sequence)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS technical_jobs_expired_claim_idx
    ON platform.technical_jobs (job_name, lease_expires_at, priority, sequence)
    WHERE status = 'running';

ALTER TABLE source_processing.job_outbox
    ADD COLUMN IF NOT EXISTS relay_claim_generation bigint NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS relay_claim_token uuid;

UPDATE source_processing.job_outbox
   SET relay_claim_generation = 1,
       relay_claim_token = gen_random_uuid()
 WHERE status = 'relaying'
   AND (relay_claim_generation = 0 OR relay_claim_token IS NULL);

ALTER TABLE source_processing.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_state_coherence;
ALTER TABLE source_processing.job_outbox
    ADD CONSTRAINT job_outbox_state_coherence CHECK (
        (status = 'pending'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL)
        OR (status = 'relaying'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NOT NULL AND relay_lease_expires_at IS NOT NULL
            AND relay_claim_generation > 0 AND relay_claim_token IS NOT NULL)
        OR (status = 'relayed'
            AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL)
    );

ALTER TABLE knowledge_access.knowledge_projections
    ADD COLUMN IF NOT EXISTS outputs_fingerprint char(64);
