CREATE TABLE IF NOT EXISTS knowledge_access.knowledge_projection_chunk_samples (
    projection_id text NOT NULL
        REFERENCES knowledge_access.knowledge_projections(projection_id)
        ON DELETE CASCADE,
    sample_ordinal integer NOT NULL CHECK (sample_ordinal > 0),
    chunk_id text NOT NULL,
    chunk_level text NOT NULL CHECK (chunk_level IN ('PARENT', 'CHILD')),
    parent_chunk_id text,
    profile_id text NOT NULL,
    profile_version text NOT NULL,
    chunk_text text NOT NULL,
    content_hash char(64) NOT NULL,
    source_locators jsonb NOT NULL CHECK (jsonb_typeof(source_locators) = 'array'),
    PRIMARY KEY (projection_id, sample_ordinal),
    UNIQUE (projection_id, chunk_id),
    CHECK (
        (chunk_level = 'PARENT' AND parent_chunk_id IS NULL)
        OR (chunk_level = 'CHILD' AND parent_chunk_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS knowledge_projection_chunk_samples_order_idx
    ON knowledge_access.knowledge_projection_chunk_samples (
        projection_id,
        sample_ordinal
    );
