ALTER TABLE source_processing.document_processing_runs
    DROP CONSTRAINT IF EXISTS document_processing_runs_status_check;
ALTER TABLE source_processing.document_processing_runs
    DROP CONSTRAINT IF EXISTS document_processing_runs_state_coherence;

ALTER TABLE source_processing.document_processing_runs
    ADD CONSTRAINT document_processing_runs_status_check CHECK (
        status IN (
            'MANIFEST_CREATED', 'DIAGNOSING', 'DIAGNOSED', 'ROUTE_PLANNED',
            'MANUAL_REVIEW', 'QUARANTINED', 'REJECTED', 'FAILED'
        )
    ),
    ADD CONSTRAINT document_processing_runs_state_coherence CHECK (
        (status IN ('MANIFEST_CREATED', 'DIAGNOSING', 'DIAGNOSED', 'ROUTE_PLANNED')
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
