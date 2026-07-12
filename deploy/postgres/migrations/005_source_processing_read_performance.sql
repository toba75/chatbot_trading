CREATE INDEX IF NOT EXISTS source_documents_editorial_duplicate_idx
    ON source_processing.source_documents (work_title, work_authors);

CREATE INDEX IF NOT EXISTS document_processing_runs_document_current_idx
    ON source_processing.document_processing_runs (document_id, created_at DESC, processing_run_id DESC);
