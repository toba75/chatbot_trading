ALTER TABLE source_processing.document_conversion_requests
    ADD COLUMN IF NOT EXISTS canonical_artifact_ref text,
    ADD COLUMN IF NOT EXISTS canonical_artifact_sha256 char(64),
    ADD COLUMN IF NOT EXISTS route_name text,
    ADD COLUMN IF NOT EXISTS tool_version text,
    ADD COLUMN IF NOT EXISTS accepted_at timestamptz;

CREATE TABLE IF NOT EXISTS source_processing.canonical_source_versions (
    canonical_version_id text PRIMARY KEY,
    canonical_source_id text NOT NULL,
    document_id text NOT NULL REFERENCES source_processing.source_documents(document_id),
    canonical_artifact_ref text NOT NULL UNIQUE,
    canonical_artifact_sha256 char(64) NOT NULL,
    route_name text NOT NULL CHECK (route_name = 'NATIVE_STANDARD'),
    tool_version text NOT NULL,
    accepted_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (document_id, canonical_version_id)
);

ALTER TABLE source_processing.document_conversion_requests
    DROP CONSTRAINT IF EXISTS document_conversion_requests_native_completion_coherence;
ALTER TABLE source_processing.document_conversion_requests
    ADD CONSTRAINT document_conversion_requests_native_completion_coherence CHECK (
        (conversion_status = 'CANONICAL_ACCEPTED'
            AND canonical_version_id IS NOT NULL
            AND rejection_error_code IS NULL
            AND canonical_artifact_ref IS NOT NULL
            AND canonical_artifact_sha256 IS NOT NULL
            AND route_name = 'NATIVE_STANDARD'
            AND tool_version IS NOT NULL
            AND accepted_at IS NOT NULL)
        OR (conversion_status = 'CONVERSION_REQUESTED'
            AND canonical_version_id IS NULL
            AND rejection_error_code IS NULL
            AND canonical_artifact_ref IS NULL
            AND canonical_artifact_sha256 IS NULL
            AND route_name IS NULL
            AND tool_version IS NULL
            AND accepted_at IS NULL)
        OR (conversion_status = 'QA_REJECTED'
            AND canonical_version_id IS NULL
            AND rejection_error_code IS NOT NULL
            AND canonical_artifact_ref IS NULL
            AND canonical_artifact_sha256 IS NULL
            AND route_name IS NULL
            AND tool_version IS NULL
            AND accepted_at IS NULL)
    );
