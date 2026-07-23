-- ADR-052 : quota Granite durable, double fencing et structures de résultats
-- de pages sans activation du fan-out ni de l'assemblage M14-local-pipeline.

DO $$
DECLARE
    identity_count integer;
BEGIN
    IF to_regclass('platform.datastore_identity') IS NULL THEN
        RAISE EXCEPTION 'MIGRATION_022_DATASTORE_IDENTITY_REQUIRED';
    END IF;
    SELECT COUNT(*) INTO identity_count FROM platform.datastore_identity;
    IF identity_count <> 1 THEN
        RAISE EXCEPTION 'DATASTORE_ENVIRONMENT_MISMATCH';
    END IF;
END $$;

CREATE TABLE platform.granite_slots (
    environment text NOT NULL
        CHECK (environment IN ('development', 'test', 'production')),
    deployment_id text NOT NULL
        CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    slot_ordinal smallint NOT NULL CHECK (slot_ordinal IN (1, 2)),
    lease_owner text,
    job_id text REFERENCES platform.technical_jobs(job_id),
    claim_generation bigint,
    claim_token uuid,
    slot_generation bigint NOT NULL CHECK (slot_generation >= 0),
    slot_token uuid,
    lease_until timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (environment, deployment_id, slot_ordinal),
    CHECK (
        (
            lease_owner IS NULL
            AND job_id IS NULL
            AND claim_generation IS NULL
            AND claim_token IS NULL
            AND slot_token IS NULL
            AND lease_until IS NULL
        )
        OR (
            lease_owner IS NOT NULL
            AND btrim(lease_owner) <> ''
            AND lease_owner = btrim(lease_owner)
            AND job_id IS NOT NULL
            AND claim_generation > 0
            AND claim_token IS NOT NULL
            AND slot_generation > 0
            AND slot_token IS NOT NULL
            AND lease_until IS NOT NULL
        )
    )
);

CREATE UNIQUE INDEX granite_slots_worker_holder_idx
    ON platform.granite_slots (environment, deployment_id, lease_owner)
    WHERE lease_owner IS NOT NULL;

CREATE INDEX granite_slots_claimable_idx
    ON platform.granite_slots (
        environment, deployment_id, lease_until, slot_ordinal
    );

INSERT INTO platform.granite_slots (
    environment,
    deployment_id,
    slot_ordinal,
    lease_owner,
    job_id,
    claim_generation,
    claim_token,
    slot_generation,
    slot_token,
    lease_until
)
SELECT
    identity.environment,
    identity.deployment_id,
    ordinal.slot_ordinal,
    NULL,
    NULL,
    NULL,
    NULL,
    0,
    NULL,
    NULL
FROM platform.datastore_identity AS identity
CROSS JOIN (VALUES (1), (2)) AS ordinal(slot_ordinal)
ON CONFLICT (environment, deployment_id, slot_ordinal) DO NOTHING;

-- Cette table appartient exclusivement à Source Processing. job_id et
-- completion_id sont des identités transportées, sans clé étrangère platform.
CREATE TABLE source_processing.page_execution_results (
    processing_run_id text NOT NULL,
    page_number integer NOT NULL CHECK (page_number > 0),
    completion_id text NOT NULL UNIQUE,
    job_id text NOT NULL,
    claim_generation bigint NOT NULL CHECK (claim_generation > 0),
    claim_token uuid NOT NULL,
    worker_instance_id text NOT NULL
        CHECK (
            btrim(worker_instance_id) <> ''
            AND worker_instance_id = btrim(worker_instance_id)
        ),
    slot_ordinal smallint,
    slot_generation bigint,
    slot_token uuid,
    result_contract_version text NOT NULL,
    route_name text NOT NULL,
    result_status text NOT NULL
        CHECK (result_status IN ('SUCCEEDED', 'FAILED', 'SKIP_EMPTY')),
    result_payload jsonb NOT NULL,
    result_fingerprint char(64) NOT NULL
        CHECK (result_fingerprint ~ '^[0-9a-f]{64}$'),
    persisted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (processing_run_id, page_number),
    FOREIGN KEY (processing_run_id, page_number)
        REFERENCES source_processing.page_manifest_entries(
            processing_run_id,
            page_number
        ),
    CHECK (
        (
            slot_ordinal IS NULL
            AND slot_generation IS NULL
            AND slot_token IS NULL
        )
        OR (
            slot_ordinal IN (1, 2)
            AND slot_generation > 0
            AND slot_token IS NOT NULL
        )
    )
);

CREATE INDEX page_execution_results_run_status_idx
    ON source_processing.page_execution_results (
        processing_run_id, result_status, page_number
    );

-- Cette outbox appartient exclusivement à platform. Elle prépare la future
-- livraison locale ADR-024 sans écrire dans Source Processing en transaction.
CREATE TABLE platform.page_completion_outbox (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    completion_id text NOT NULL UNIQUE,
    environment text NOT NULL
        CHECK (environment IN ('development', 'test', 'production')),
    deployment_id text NOT NULL
        CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    job_id text NOT NULL REFERENCES platform.technical_jobs(job_id),
    claim_generation bigint NOT NULL CHECK (claim_generation > 0),
    claim_token uuid NOT NULL,
    worker_instance_id text NOT NULL
        CHECK (
            btrim(worker_instance_id) <> ''
            AND worker_instance_id = btrim(worker_instance_id)
        ),
    slot_ordinal smallint,
    slot_generation bigint,
    slot_token uuid,
    payload jsonb NOT NULL,
    payload_fingerprint char(64) NOT NULL
        CHECK (payload_fingerprint ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('pending', 'relaying', 'relayed')),
    relay_owner text,
    relay_lease_until timestamptz,
    relay_generation bigint NOT NULL CHECK (relay_generation >= 0),
    relay_token uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    relayed_at timestamptz,
    CHECK (
        (
            slot_ordinal IS NULL
            AND slot_generation IS NULL
            AND slot_token IS NULL
        )
        OR (
            slot_ordinal IN (1, 2)
            AND slot_generation > 0
            AND slot_token IS NOT NULL
        )
    ),
    CHECK (
        (
            status = 'pending'
            AND relay_owner IS NULL
            AND relay_lease_until IS NULL
            AND relay_token IS NULL
            AND relayed_at IS NULL
        )
        OR (
            status = 'relaying'
            AND relay_owner IS NOT NULL
            AND relay_lease_until IS NOT NULL
            AND relay_generation > 0
            AND relay_token IS NOT NULL
            AND relayed_at IS NULL
        )
        OR (
            status = 'relayed'
            AND relay_owner IS NULL
            AND relay_lease_until IS NULL
            AND relay_token IS NULL
            AND relayed_at IS NOT NULL
        )
    )
);

CREATE INDEX page_completion_outbox_claim_idx
    ON platform.page_completion_outbox (
        environment, deployment_id, status, relay_lease_until, sequence
    );
