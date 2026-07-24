-- T-005 : le parcours du job parent est figé avant le fan-out. La migration
-- classe explicitement les demandes antérieures comme m004-inline-v1 ; elle
-- n'active aucun traitement distribué existant.

ALTER TABLE source_processing.document_conversion_requests
    ADD COLUMN orchestration_version text;

UPDATE source_processing.document_conversion_requests
   SET orchestration_version = 'm004-inline-v1'
 WHERE orchestration_version IS NULL;

ALTER TABLE source_processing.document_conversion_requests
    ALTER COLUMN orchestration_version SET NOT NULL,
    ADD CONSTRAINT document_conversion_orchestration_version_check CHECK (
        orchestration_version IN ('m004-inline-v1', 'm014-page-fanout-v1')
    );

CREATE TABLE source_processing.document_page_fanouts (
    processing_run_id text PRIMARY KEY
        REFERENCES source_processing.document_processing_runs(processing_run_id),
    document_id text NOT NULL UNIQUE
        REFERENCES source_processing.document_conversion_requests(document_id),
    orchestration_version text NOT NULL
        CHECK (orchestration_version = 'm014-page-fanout-v1'),
    environment text NOT NULL
        CHECK (environment IN ('development', 'test', 'production')),
    deployment_id text NOT NULL
        CHECK (deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
    configuration_hash char(64) NOT NULL
        CHECK (configuration_hash ~ '^[0-9a-f]{64}$'),
    page_manifest_sha256 char(64) NOT NULL
        CHECK (page_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    total_units integer NOT NULL CHECK (total_units > 0),
    fan_out_payload jsonb NOT NULL,
    fan_out_fingerprint char(64) NOT NULL
        CHECK (fan_out_fingerprint ~ '^[0-9a-f]{64}$'),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX document_page_fanouts_identity_idx
    ON source_processing.document_page_fanouts (
        environment,
        deployment_id,
        configuration_hash,
        fan_out_fingerprint
    );
