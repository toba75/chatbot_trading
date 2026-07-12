CREATE SCHEMA IF NOT EXISTS source_processing;
CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE IF NOT EXISTS source_processing.source_documents (
    document_id text PRIMARY KEY,
    fingerprint char(64) NOT NULL UNIQUE,
    original_storage_ref text NOT NULL UNIQUE,
    title text NOT NULL,
    authors text[] NOT NULL,
    publication_year integer NOT NULL CHECK (publication_year > 0),
    edition text NOT NULL,
    work_title text NOT NULL,
    work_authors text[] NOT NULL,
    status text NOT NULL CHECK (status IN ('REGISTERED', 'QUARANTINED')),
    quarantine_reason text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status = 'REGISTERED' AND quarantine_reason IS NULL)
        OR (status = 'QUARANTINED' AND quarantine_reason IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS source_processing.document_processing_runs (
    processing_run_id text PRIMARY KEY,
    document_id text NOT NULL UNIQUE
        REFERENCES source_processing.source_documents(document_id),
    source_page_count integer NOT NULL CHECK (source_page_count > 0),
    status text NOT NULL CHECK (
        status IN (
            'MANIFEST_CREATED', 'DIAGNOSED', 'ROUTE_PLANNED',
            'MANUAL_REVIEW', 'QUARANTINED', 'REJECTED'
        )
    ),
    manual_review_reason text,
    blocking_policy_version text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status IN ('MANIFEST_CREATED', 'DIAGNOSED', 'ROUTE_PLANNED')
            AND manual_review_reason IS NULL AND blocking_policy_version IS NULL)
        OR (status IN ('MANUAL_REVIEW', 'QUARANTINED', 'REJECTED')
            AND manual_review_reason IS NOT NULL AND blocking_policy_version IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS source_processing.page_manifest_entries (
    processing_run_id text NOT NULL
        REFERENCES source_processing.document_processing_runs(processing_run_id)
        ON DELETE CASCADE,
    page_number integer NOT NULL CHECK (page_number > 0),
    state text NOT NULL CHECK (state IN ('PRESENT', 'EMPTY', 'UNREADABLE', 'REJECTED')),
    PRIMARY KEY (processing_run_id, page_number)
);

CREATE TABLE IF NOT EXISTS source_processing.page_decisions (
    processing_run_id text NOT NULL
        REFERENCES source_processing.document_processing_runs(processing_run_id)
        ON DELETE CASCADE,
    page_number integer NOT NULL CHECK (page_number > 0),
    page_state text NOT NULL,
    native_text_state text NOT NULL,
    image_state text NOT NULL,
    existing_ocr_state text NOT NULL,
    layout_complexity text NOT NULL,
    corruption_state text NOT NULL,
    mixed_content_detected boolean NOT NULL,
    has_table boolean NOT NULL,
    has_formula boolean NOT NULL,
    diagnostic_version text NOT NULL,
    justification text NOT NULL,
    PRIMARY KEY (processing_run_id, page_number),
    FOREIGN KEY (processing_run_id, page_number)
        REFERENCES source_processing.page_manifest_entries(processing_run_id, page_number)
);

CREATE TABLE IF NOT EXISTS source_processing.route_plans (
    processing_run_id text PRIMARY KEY
        REFERENCES source_processing.document_processing_runs(processing_run_id)
        ON DELETE CASCADE,
    routing_policy_version text NOT NULL,
    dominant_route_name text NOT NULL,
    confidence_score double precision NOT NULL
        CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

CREATE TABLE IF NOT EXISTS source_processing.page_routes (
    processing_run_id text NOT NULL
        REFERENCES source_processing.route_plans(processing_run_id)
        ON DELETE CASCADE,
    page_number integer NOT NULL CHECK (page_number > 0),
    route_name text NOT NULL,
    decision_mode text NOT NULL,
    confidence_score double precision NOT NULL
        CHECK (confidence_score >= 0 AND confidence_score <= 1),
    preprocessing_action text NOT NULL,
    routing_policy_version text NOT NULL,
    justification text NOT NULL,
    is_exception boolean NOT NULL,
    PRIMARY KEY (processing_run_id, page_number),
    FOREIGN KEY (processing_run_id, page_number)
        REFERENCES source_processing.page_decisions(processing_run_id, page_number)
);

CREATE TABLE IF NOT EXISTS platform.technical_jobs (
    sequence bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id text GENERATED ALWAYS AS (
        'JOB-M002-' || lpad(sequence::text, 6, '0')
    ) STORED UNIQUE,
    job_name text NOT NULL,
    priority text NOT NULL CHECK (priority IN ('P0', 'P1', 'P2', 'P3', 'P4', 'P5')),
    input_hash char(64) NOT NULL,
    configuration_hash char(64) NOT NULL,
    code_version text NOT NULL,
    model_version text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'failed')),
    result jsonb,
    failure_reason text,
    recalculation_number integer NOT NULL CHECK (recalculation_number >= 0),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (status = 'succeeded' AND result IS NOT NULL AND failure_reason IS NULL)
        OR (status = 'failed' AND result IS NULL AND failure_reason IS NOT NULL)
        OR (status IN ('pending', 'running') AND result IS NULL AND failure_reason IS NULL)
    ),
    UNIQUE (
        job_name, input_hash, configuration_hash, code_version,
        model_version, recalculation_number
    )
);

CREATE TABLE IF NOT EXISTS source_processing.document_conversion_requests (
    document_id text PRIMARY KEY
        REFERENCES source_processing.source_documents(document_id),
    conversion_status text NOT NULL CHECK (
        conversion_status IN ('CONVERSION_REQUESTED', 'QA_REJECTED', 'CANONICAL_ACCEPTED')
    ),
    canonical_version_id text,
    rejection_error_code text,
    job_id text NOT NULL UNIQUE REFERENCES platform.technical_jobs(job_id),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (
        (conversion_status = 'CONVERSION_REQUESTED'
            AND canonical_version_id IS NULL AND rejection_error_code IS NULL)
        OR (conversion_status = 'QA_REJECTED'
            AND canonical_version_id IS NULL AND rejection_error_code IS NOT NULL)
        OR (conversion_status = 'CANONICAL_ACCEPTED'
            AND canonical_version_id IS NOT NULL AND rejection_error_code IS NULL)
    )
);
