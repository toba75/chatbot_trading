ALTER TABLE source_processing.document_conversion_requests
    ADD COLUMN IF NOT EXISTS execution_phase text,
    ADD COLUMN IF NOT EXISTS completed_units integer,
    ADD COLUMN IF NOT EXISTS total_units integer,
    ADD COLUMN IF NOT EXISTS failure_error_code text;

UPDATE source_processing.document_conversion_requests AS conversion
   SET execution_phase = CASE conversion.conversion_status
           WHEN 'CONVERSION_REQUESTED' THEN 'QUEUED'
           WHEN 'CANONICAL_ACCEPTED' THEN 'SUCCEEDED'
           WHEN 'QA_REJECTED' THEN 'FAILED'
       END,
       completed_units = CASE conversion.conversion_status
           WHEN 'CANONICAL_ACCEPTED' THEN run.source_page_count
           ELSE 0
       END,
       total_units = run.source_page_count,
       failure_error_code = CASE conversion.conversion_status
           WHEN 'QA_REJECTED' THEN conversion.rejection_error_code
           ELSE NULL
       END
  FROM source_processing.document_processing_runs AS run
 WHERE run.document_id = conversion.document_id
   AND conversion.execution_phase IS NULL;

ALTER TABLE source_processing.document_conversion_requests
    ALTER COLUMN execution_phase SET NOT NULL,
    ALTER COLUMN completed_units SET NOT NULL,
    ALTER COLUMN total_units SET NOT NULL;

ALTER TABLE source_processing.document_conversion_requests
    DROP CONSTRAINT IF EXISTS document_conversion_requests_native_completion_coherence;
ALTER TABLE source_processing.document_conversion_requests
    ADD CONSTRAINT document_conversion_requests_native_completion_coherence CHECK (
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
            AND route_name = 'NATIVE_STANDARD'
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
