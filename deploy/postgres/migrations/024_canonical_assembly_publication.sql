-- T-007 : publication canonique M-014 et événement métier dans une transaction SP.

ALTER TABLE source_processing.canonical_source_versions
    ADD COLUMN canonical_assembly_id char(64),
    ADD COLUMN page_count integer,
    ADD COLUMN quality_policy_version text,
    ADD COLUMN canonical_result_fingerprint char(64),
    ADD CONSTRAINT canonical_source_versions_assembly_coherence CHECK (
        (
            canonical_assembly_id IS NULL
            AND page_count IS NULL
            AND quality_policy_version IS NULL
            AND canonical_result_fingerprint IS NULL
        )
        OR (
            canonical_assembly_id IS NOT NULL
            AND page_count IS NOT NULL
            AND quality_policy_version IS NOT NULL
            AND canonical_result_fingerprint IS NOT NULL
            AND canonical_assembly_id ~ '^[0-9a-f]{64}$'
            AND page_count > 0
            AND btrim(quality_policy_version) <> ''
            AND quality_policy_version = btrim(quality_policy_version)
            AND canonical_result_fingerprint ~ '^[0-9a-f]{64}$'
        )
    );

CREATE UNIQUE INDEX canonical_source_versions_assembly_id_idx
    ON source_processing.canonical_source_versions (canonical_assembly_id)
    WHERE canonical_assembly_id IS NOT NULL;

CREATE TABLE source_processing.canonical_publication_outbox (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id text NOT NULL UNIQUE,
    canonical_version_id text NOT NULL UNIQUE
        REFERENCES source_processing.canonical_source_versions(canonical_version_id),
    environment text NOT NULL
        CHECK (environment IN ('development', 'test', 'production')),
    deployment_id text NOT NULL
        CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    configuration_hash char(64) NOT NULL
        CHECK (configuration_hash ~ '^[0-9a-f]{64}$'),
    event_payload jsonb NOT NULL,
    event_fingerprint char(64) NOT NULL
        CHECK (event_fingerprint ~ '^[0-9a-f]{64}$'),
    status text NOT NULL CHECK (status IN ('pending', 'relaying', 'relayed')),
    relay_owner text,
    relay_lease_until timestamptz,
    relay_generation bigint NOT NULL CHECK (relay_generation >= 0),
    relay_token uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    relayed_at timestamptz,
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

CREATE INDEX canonical_publication_outbox_claim_idx
    ON source_processing.canonical_publication_outbox (
        environment, deployment_id, status, relay_lease_until, sequence
    );
