ALTER TABLE source_processing.document_processing_runs
    ADD COLUMN IF NOT EXISTS failure_error_code text;

ALTER TABLE source_processing.document_processing_runs
    DROP CONSTRAINT IF EXISTS document_processing_runs_status_check;
ALTER TABLE source_processing.document_processing_runs
    DROP CONSTRAINT IF EXISTS document_processing_runs_check;
ALTER TABLE source_processing.document_processing_runs
    DROP CONSTRAINT IF EXISTS document_processing_runs_state_coherence;

ALTER TABLE source_processing.document_processing_runs
    ADD CONSTRAINT document_processing_runs_status_check CHECK (
        status IN (
            'MANIFEST_CREATED', 'DIAGNOSED', 'ROUTE_PLANNED',
            'MANUAL_REVIEW', 'QUARANTINED', 'REJECTED', 'FAILED'
        )
    ),
    ADD CONSTRAINT document_processing_runs_state_coherence CHECK (
        (status IN ('MANIFEST_CREATED', 'DIAGNOSED', 'ROUTE_PLANNED')
            AND manual_review_reason IS NULL
            AND blocking_policy_version IS NULL
            AND failure_error_code IS NULL)
        OR (status IN ('MANUAL_REVIEW', 'QUARANTINED', 'REJECTED')
            AND manual_review_reason IS NOT NULL
            AND blocking_policy_version IS NOT NULL
            AND failure_error_code IS NULL)
        OR (status = 'FAILED'
            AND manual_review_reason IS NULL
            AND blocking_policy_version IS NULL
            AND failure_error_code IS NOT NULL)
    );

ALTER TABLE knowledge_access.knowledge_projections
    ADD COLUMN IF NOT EXISTS aggregate_version bigint;
UPDATE knowledge_access.knowledge_projections
   SET aggregate_version = 0
 WHERE aggregate_version IS NULL;
ALTER TABLE knowledge_access.knowledge_projections
    ALTER COLUMN aggregate_version SET NOT NULL;
ALTER TABLE knowledge_access.knowledge_projections
    DROP CONSTRAINT IF EXISTS knowledge_projections_aggregate_version_check;
ALTER TABLE knowledge_access.knowledge_projections
    ADD CONSTRAINT knowledge_projections_aggregate_version_check
    CHECK (aggregate_version >= 0);
