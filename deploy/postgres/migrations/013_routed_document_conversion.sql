ALTER TABLE source_processing.canonical_source_versions
    DROP CONSTRAINT IF EXISTS canonical_source_versions_route_name_check;
ALTER TABLE source_processing.canonical_source_versions
    ADD CONSTRAINT canonical_source_versions_route_name_check CHECK (
        route_name IN (
            'NATIVE_STANDARD',
            'SCAN_GRANITE',
            'PREPROCESS_GRANITE',
            'BAD_OCR_TO_GRANITE',
            'MIXED_PAGEWISE',
            'TARGETED_ENRICHMENT'
        )
    );

ALTER TABLE source_processing.document_conversion_requests
    DROP CONSTRAINT IF EXISTS document_conversion_requests_native_completion_coherence;
ALTER TABLE source_processing.document_conversion_requests
    DROP CONSTRAINT IF EXISTS document_conversion_requests_routed_completion_coherence;
ALTER TABLE source_processing.document_conversion_requests
    ADD CONSTRAINT document_conversion_requests_routed_completion_coherence CHECK (
        (conversion_status = 'CONVERSION_REQUESTED'
            AND execution_phase IN ('QUEUED', 'RUNNING')
            AND completed_units = 0
            AND total_units > 0
            AND canonical_version_id IS NULL
            AND rejection_error_code IS NULL
            AND failure_error_code IS NULL
            AND canonical_artifact_ref IS NULL
            AND canonical_artifact_sha256 IS NULL
            AND route_name IS NULL
            AND tool_version IS NULL
            AND accepted_at IS NULL)
        OR (conversion_status = 'CANONICAL_ACCEPTED'
            AND execution_phase = 'SUCCEEDED'
            AND completed_units = total_units
            AND total_units > 0
            AND canonical_version_id IS NOT NULL
            AND rejection_error_code IS NULL
            AND failure_error_code IS NULL
            AND canonical_artifact_ref IS NOT NULL
            AND canonical_artifact_sha256 IS NOT NULL
            AND route_name IN (
                'NATIVE_STANDARD',
                'SCAN_GRANITE',
                'PREPROCESS_GRANITE',
                'BAD_OCR_TO_GRANITE',
                'MIXED_PAGEWISE',
                'TARGETED_ENRICHMENT'
            )
            AND tool_version IS NOT NULL
            AND accepted_at IS NOT NULL)
        OR (conversion_status = 'QA_REJECTED'
            AND execution_phase = 'FAILED'
            AND completed_units >= 0
            AND completed_units < total_units
            AND total_units > 0
            AND canonical_version_id IS NULL
            AND rejection_error_code IS NOT NULL
            AND failure_error_code = rejection_error_code
            AND canonical_artifact_ref IS NULL
            AND canonical_artifact_sha256 IS NULL
            AND route_name IS NULL
            AND tool_version IS NULL
            AND accepted_at IS NULL)
    );
