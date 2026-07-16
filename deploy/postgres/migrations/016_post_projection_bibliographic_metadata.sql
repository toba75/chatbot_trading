ALTER TABLE source_processing.source_documents
    ALTER COLUMN title DROP NOT NULL,
    ALTER COLUMN authors DROP NOT NULL,
    ALTER COLUMN publication_year DROP NOT NULL,
    ALTER COLUMN edition DROP NOT NULL,
    ALTER COLUMN work_title DROP NOT NULL,
    ALTER COLUMN work_authors DROP NOT NULL;

ALTER TABLE knowledge_access.knowledge_projections
    ADD COLUMN bibliographic_metadata_status text NOT NULL DEFAULT 'PENDING',
    ADD COLUMN bibliographic_title text,
    ADD COLUMN bibliographic_authors text[],
    ADD COLUMN bibliographic_publication_year integer,
    ADD COLUMN bibliographic_edition text,
    ADD COLUMN bibliographic_evidence jsonb,
    ADD COLUMN bibliographic_model_id text,
    ADD COLUMN bibliographic_model_revision text,
    ADD COLUMN bibliographic_runtime_version text;

UPDATE knowledge_access.knowledge_projections AS projection
   SET bibliographic_metadata_status = 'LEGACY_DECLARED',
       bibliographic_title = source.title,
       bibliographic_authors = source.authors,
       bibliographic_publication_year = source.publication_year,
       bibliographic_edition = source.edition
  FROM source_processing.source_documents AS source
 WHERE source.document_id = projection.document_id
   AND source.title IS NOT NULL
   AND source.authors IS NOT NULL;

ALTER TABLE knowledge_access.knowledge_projections
    ADD CONSTRAINT knowledge_projection_bibliographic_metadata_check CHECK (
        bibliographic_metadata_status IN ('PENDING', 'EXTRACTED', 'LEGACY_DECLARED')
        AND (
            (bibliographic_metadata_status = 'PENDING'
                AND bibliographic_title IS NULL
                AND bibliographic_authors IS NULL
                AND bibliographic_publication_year IS NULL
                AND bibliographic_edition IS NULL
                AND bibliographic_evidence IS NULL
                AND bibliographic_model_id IS NULL
                AND bibliographic_model_revision IS NULL
                AND bibliographic_runtime_version IS NULL)
            OR (bibliographic_metadata_status = 'LEGACY_DECLARED'
                AND bibliographic_title IS NOT NULL
                AND cardinality(bibliographic_authors) > 0
                AND bibliographic_evidence IS NULL
                AND bibliographic_model_id IS NULL
                AND bibliographic_model_revision IS NULL
                AND bibliographic_runtime_version IS NULL)
            OR (bibliographic_metadata_status = 'EXTRACTED'
                AND bibliographic_title IS NOT NULL
                AND cardinality(bibliographic_authors) > 0
                AND bibliographic_evidence IS NOT NULL
                AND bibliographic_model_id IS NOT NULL
                AND bibliographic_model_revision IS NOT NULL
                AND bibliographic_runtime_version IS NOT NULL)
        )
        AND (
            bibliographic_publication_year IS NULL
            OR bibliographic_publication_year BETWEEN 1 AND 9999
        )
    );
