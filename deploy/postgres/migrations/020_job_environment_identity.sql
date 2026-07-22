-- ADR-045 : toute enveloppe asynchrone porte l'identité de son installation.
-- Un refus terminal utilise le code stable WORKER_ENVIRONMENT_MISMATCH.

ALTER TABLE platform.technical_jobs
    ADD COLUMN IF NOT EXISTS environment text,
    ADD COLUMN IF NOT EXISTS deployment_id text;

ALTER TABLE source_processing.job_outbox
    ADD COLUMN IF NOT EXISTS environment text,
    ADD COLUMN IF NOT EXISTS deployment_id text,
    ADD COLUMN IF NOT EXISTS failure_error_code text;

ALTER TABLE knowledge_access.job_outbox
    ADD COLUMN IF NOT EXISTS environment text,
    ADD COLUMN IF NOT EXISTS deployment_id text,
    ADD COLUMN IF NOT EXISTS failure_error_code text;

DO $$
DECLARE
    identity_count integer;
BEGIN
    IF to_regclass('platform.datastore_identity') IS NULL THEN
        RAISE EXCEPTION 'MIGRATION_020_LEGACY_ADOPTION_REQUIRED';
    END IF;
    SELECT COUNT(*) INTO identity_count FROM platform.datastore_identity;
    IF identity_count <> 1 THEN
        RAISE EXCEPTION 'DATASTORE_ENVIRONMENT_MISMATCH';
    END IF;
END $$;

UPDATE platform.technical_jobs AS job
   SET environment = identity.environment,
       deployment_id = identity.deployment_id
  FROM platform.datastore_identity AS identity
 WHERE job.environment IS NULL OR job.deployment_id IS NULL;

UPDATE source_processing.job_outbox AS message
   SET environment = identity.environment,
       deployment_id = identity.deployment_id
  FROM platform.datastore_identity AS identity
 WHERE message.environment IS NULL OR message.deployment_id IS NULL;

UPDATE knowledge_access.job_outbox AS message
   SET environment = identity.environment,
       deployment_id = identity.deployment_id
  FROM platform.datastore_identity AS identity
 WHERE message.environment IS NULL OR message.deployment_id IS NULL;

ALTER TABLE platform.technical_jobs
    ALTER COLUMN environment SET NOT NULL,
    ALTER COLUMN deployment_id SET NOT NULL;
ALTER TABLE source_processing.job_outbox
    ALTER COLUMN environment SET NOT NULL,
    ALTER COLUMN deployment_id SET NOT NULL;
ALTER TABLE knowledge_access.job_outbox
    ALTER COLUMN environment SET NOT NULL,
    ALTER COLUMN deployment_id SET NOT NULL;

-- Expand/backfill/contract : les contraintes sont ajoutées NOT VALID pour
-- coexister avec le déploiement historique, puis validées après le backfill.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'platform.technical_jobs'::regclass
           AND conname = 'technical_jobs_environment_check'
    ) THEN
        ALTER TABLE platform.technical_jobs
            ADD CONSTRAINT technical_jobs_environment_check
            CHECK (environment IN ('development', 'test', 'production')) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'platform.technical_jobs'::regclass
           AND conname = 'technical_jobs_deployment_id_check'
    ) THEN
        ALTER TABLE platform.technical_jobs
            ADD CONSTRAINT technical_jobs_deployment_id_check
            CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$') NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'source_processing.job_outbox'::regclass
           AND conname = 'source_processing_job_outbox_environment_check'
    ) THEN
        ALTER TABLE source_processing.job_outbox
            ADD CONSTRAINT source_processing_job_outbox_environment_check
            CHECK (environment IN ('development', 'test', 'production')) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'source_processing.job_outbox'::regclass
           AND conname = 'source_processing_job_outbox_deployment_id_check'
    ) THEN
        ALTER TABLE source_processing.job_outbox
            ADD CONSTRAINT source_processing_job_outbox_deployment_id_check
            CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$') NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'knowledge_access.job_outbox'::regclass
           AND conname = 'knowledge_access_job_outbox_environment_check'
    ) THEN
        ALTER TABLE knowledge_access.job_outbox
            ADD CONSTRAINT knowledge_access_job_outbox_environment_check
            CHECK (environment IN ('development', 'test', 'production')) NOT VALID;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'knowledge_access.job_outbox'::regclass
           AND conname = 'knowledge_access_job_outbox_deployment_id_check'
    ) THEN
        ALTER TABLE knowledge_access.job_outbox
            ADD CONSTRAINT knowledge_access_job_outbox_deployment_id_check
            CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$') NOT VALID;
    END IF;
END $$;

ALTER TABLE platform.technical_jobs
    VALIDATE CONSTRAINT technical_jobs_environment_check,
    VALIDATE CONSTRAINT technical_jobs_deployment_id_check;
ALTER TABLE source_processing.job_outbox
    VALIDATE CONSTRAINT source_processing_job_outbox_environment_check,
    VALIDATE CONSTRAINT source_processing_job_outbox_deployment_id_check;
ALTER TABLE knowledge_access.job_outbox
    VALIDATE CONSTRAINT knowledge_access_job_outbox_environment_check,
    VALIDATE CONSTRAINT knowledge_access_job_outbox_deployment_id_check;

ALTER TABLE source_processing.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_status_check,
    DROP CONSTRAINT IF EXISTS job_outbox_state_coherence;
ALTER TABLE source_processing.job_outbox
    ADD CONSTRAINT job_outbox_status_check
        CHECK (status IN ('pending', 'relaying', 'relayed', 'failed')),
    ADD CONSTRAINT job_outbox_state_coherence CHECK (
        (status = 'pending'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'relaying'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NOT NULL AND relay_lease_expires_at IS NOT NULL
            AND relay_claim_generation > 0 AND relay_claim_token IS NOT NULL
            AND failure_error_code IS NULL)
        OR (status = 'relayed'
            AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'failed'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL
            AND failure_error_code = 'WORKER_ENVIRONMENT_MISMATCH')
    );

ALTER TABLE knowledge_access.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_status_check,
    DROP CONSTRAINT IF EXISTS knowledge_access_job_outbox_state_coherence;
ALTER TABLE knowledge_access.job_outbox
    ADD CONSTRAINT job_outbox_status_check
        CHECK (status IN ('pending', 'relaying', 'relayed', 'failed')),
    ADD CONSTRAINT knowledge_access_job_outbox_state_coherence CHECK (
        (status = 'pending'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'relaying'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NOT NULL AND relay_lease_expires_at IS NOT NULL
            AND relay_claim_generation > 0 AND relay_claim_token IS NOT NULL
            AND failure_error_code IS NULL)
        OR (status = 'relayed'
            AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'failed'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL
            AND failure_error_code = 'WORKER_ENVIRONMENT_MISMATCH')
    );

CREATE INDEX IF NOT EXISTS technical_jobs_environment_claim_idx
    ON platform.technical_jobs (
        environment, deployment_id, job_name, priority, sequence
    )
    WHERE status IN ('pending', 'running');

CREATE INDEX IF NOT EXISTS source_processing_job_outbox_environment_claim_idx
    ON source_processing.job_outbox (environment, deployment_id, sequence)
    WHERE status IN ('pending', 'relaying');

CREATE INDEX IF NOT EXISTS knowledge_access_job_outbox_environment_claim_idx
    ON knowledge_access.job_outbox (environment, deployment_id, sequence)
    WHERE status IN ('pending', 'relaying');
