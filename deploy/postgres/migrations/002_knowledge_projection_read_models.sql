CREATE SCHEMA IF NOT EXISTS knowledge_access;

CREATE TABLE IF NOT EXISTS knowledge_access.knowledge_projections (
    projection_id text PRIMARY KEY,
    document_id text NOT NULL,
    canonical_version_id text NOT NULL,
    projection_profile_id text NOT NULL,
    chunking_profile text NOT NULL,
    embedding_model text NOT NULL,
    sparse_profile text NOT NULL,
    index_schema text NOT NULL,
    build_fingerprint char(64) NOT NULL UNIQUE,
    status text NOT NULL CHECK (
        status IN (
            'REQUESTED', 'BUILDING', 'BUILT', 'INDEXING',
            'SEARCHABLE', 'STALE', 'FAILED', 'RETIRED'
        )
    ),
    chunk_count integer NOT NULL CHECK (chunk_count >= 0),
    state_observed_at timestamptz NOT NULL,
    UNIQUE (document_id, canonical_version_id, projection_profile_id)
);

CREATE INDEX IF NOT EXISTS knowledge_projections_document_current_idx
    ON knowledge_access.knowledge_projections (document_id, state_observed_at DESC);
