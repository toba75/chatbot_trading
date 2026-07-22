-- Corrige sans drift les installations ayant déjà appliqué la migration 020.
-- Cette migration est rejouable : les contraintes sont créées seulement si
-- elles manquent, puis leur validation est exigée explicitement.

DO $$
DECLARE
    identity_count integer;
BEGIN
    IF to_regclass('platform.datastore_identity') IS NULL THEN
        RAISE EXCEPTION 'MIGRATION_021_DATASTORE_IDENTITY_REQUIRED';
    END IF;
    SELECT COUNT(*) INTO identity_count FROM platform.datastore_identity;
    IF identity_count <> 1 THEN
        RAISE EXCEPTION 'DATASTORE_ENVIRONMENT_MISMATCH';
    END IF;
END $$;

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
