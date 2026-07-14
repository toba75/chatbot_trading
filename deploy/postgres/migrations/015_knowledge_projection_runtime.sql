ALTER TABLE knowledge_access.knowledge_projections
    ADD COLUMN IF NOT EXISTS execution_phase text NOT NULL DEFAULT 'QUEUED',
    ADD COLUMN IF NOT EXISTS completed_units integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_units integer NOT NULL DEFAULT 1,
    ADD COLUMN IF NOT EXISTS failure_error_code text;

UPDATE knowledge_access.knowledge_projections
   SET execution_phase = CASE
           WHEN status = 'REQUESTED' THEN 'QUEUED'
           WHEN status IN ('SEARCHABLE', 'STALE', 'RETIRED') THEN 'SUCCEEDED'
           WHEN status = 'FAILED' THEN 'FAILED'
           ELSE 'RUNNING'
       END,
       completed_units = CASE WHEN status IN ('SEARCHABLE', 'STALE', 'RETIRED') THEN GREATEST(chunk_count, 1) ELSE 0 END,
       total_units = CASE WHEN status IN ('SEARCHABLE', 'STALE', 'RETIRED') THEN GREATEST(chunk_count, 1) ELSE 1 END,
       failure_error_code = CASE WHEN status = 'FAILED' THEN 'PROJECTION_PRE_RUNTIME_FAILURE' ELSE NULL END;

ALTER TABLE knowledge_access.knowledge_projections
    DROP CONSTRAINT IF EXISTS knowledge_projections_execution_progress_check;
ALTER TABLE knowledge_access.knowledge_projections
    ADD CONSTRAINT knowledge_projections_execution_progress_check CHECK (
        completed_units >= 0
        AND total_units >= 1
        AND completed_units <= total_units
        AND execution_phase IN ('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED')
        AND (
            (execution_phase = 'QUEUED'
                AND status = 'REQUESTED'
                AND completed_units = 0
                AND failure_error_code IS NULL)
            OR (execution_phase = 'RUNNING'
                AND status IN ('BUILDING', 'BUILT', 'INDEXING')
                AND failure_error_code IS NULL)
            OR (execution_phase = 'SUCCEEDED'
                AND status IN ('SEARCHABLE', 'STALE', 'RETIRED')
                AND completed_units = total_units
                AND failure_error_code IS NULL)
            OR (execution_phase = 'FAILED'
                AND status = 'FAILED'
                AND failure_error_code IS NOT NULL)
        )
    );

CREATE TABLE IF NOT EXISTS knowledge_access.job_outbox (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    outbox_id text GENERATED ALWAYS AS (
        'OUTBOX-KA-' || lpad(sequence::text, 10, '0')
    ) STORED UNIQUE,
    job_name text NOT NULL CHECK (job_name = 'PROJECT_DOCUMENT'),
    priority text NOT NULL CHECK (priority IN ('P0', 'P1', 'P2', 'P3', 'P4', 'P5')),
    input_hash char(64) NOT NULL,
    configuration_hash char(64) NOT NULL,
    code_version text NOT NULL,
    model_version text NOT NULL,
    payload jsonb NOT NULL,
    trace_id text NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'relaying', 'relayed')),
    relay_attempts integer NOT NULL DEFAULT 0 CHECK (relay_attempts >= 0),
    platform_job_id text UNIQUE,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    relayed_at timestamptz,
    relay_owner text,
    relay_lease_expires_at timestamptz,
    relay_claim_generation bigint NOT NULL DEFAULT 0,
    relay_claim_token uuid,
    CONSTRAINT knowledge_access_job_outbox_state_coherence CHECK (
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
    ),
    UNIQUE (job_name, input_hash, configuration_hash, code_version, model_version)
);

CREATE INDEX IF NOT EXISTS knowledge_access_job_outbox_relay_claim_idx
    ON knowledge_access.job_outbox (sequence)
    WHERE status IN ('pending', 'relaying');
