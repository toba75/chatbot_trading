-- T-008 : relais SP vers KA, projection locale et preuve de génération Qdrant.

CREATE TABLE knowledge_access.canonical_publication_inbox (
    event_id text PRIMARY KEY,
    event_fingerprint char(64) NOT NULL
        CHECK (event_fingerprint ~ '^[0-9a-f]{64}$'),
    canonical_version_id text NOT NULL UNIQUE,
    document_id text NOT NULL,
    canonical_artifact_ref text NOT NULL UNIQUE,
    canonical_artifact_sha256 char(64) NOT NULL
        CHECK (canonical_artifact_sha256 ~ '^[0-9a-f]{64}$'),
    environment text NOT NULL
        CHECK (environment IN ('development', 'test', 'production')),
    deployment_id text NOT NULL
        CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    configuration_hash char(64) NOT NULL
        CHECK (configuration_hash ~ '^[0-9a-f]{64}$'),
    event_payload jsonb NOT NULL,
    received_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE knowledge_access.projection_event_receipts (
    event_id text PRIMARY KEY
        REFERENCES knowledge_access.canonical_publication_inbox(event_id),
    event_fingerprint char(64) NOT NULL
        CHECK (event_fingerprint ~ '^[0-9a-f]{64}$'),
    projection_id text NOT NULL,
    delivery_count integer NOT NULL DEFAULT 1 CHECK (delivery_count >= 1),
    processed_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_delivered_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE knowledge_access.knowledge_projections
    ADD COLUMN environment text,
    ADD COLUMN deployment_id text,
    ADD COLUMN configuration_hash char(64),
    ADD COLUMN qdrant_collection_name text,
    ADD COLUMN index_generation text,
    ADD CONSTRAINT knowledge_projections_environment_coherence CHECK (
        (
            environment IS NULL
            AND deployment_id IS NULL
            AND configuration_hash IS NULL
            AND qdrant_collection_name IS NULL
        )
        OR (
            environment IN ('development', 'test', 'production')
            AND deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            AND configuration_hash ~ '^[0-9a-f]{64}$'
            AND btrim(qdrant_collection_name) <> ''
            AND qdrant_collection_name = btrim(qdrant_collection_name)
        )
    ),
    ADD CONSTRAINT knowledge_projections_generation_coherence CHECK (
        (status = 'SEARCHABLE' AND index_generation IS NOT NULL)
        OR (status <> 'SEARCHABLE')
    ) NOT VALID;

CREATE INDEX knowledge_projections_environment_idx
    ON knowledge_access.knowledge_projections (
        environment, deployment_id, configuration_hash, status
    )
    WHERE environment IS NOT NULL;
