-- M-014 : lookup borné du contrat CONVERT_PAGE figé dans l'outbox SP.
-- L'index texte évite tout cast risqué sur les payloads historiques étrangers.

CREATE INDEX IF NOT EXISTS source_processing_job_outbox_convert_page_lookup_idx
    ON source_processing.job_outbox (
        (payload ->> 'processing_run_id'),
        (payload ->> 'page_number')
    )
    WHERE job_name = 'CONVERT_PAGE';
