CREATE TABLE IF NOT EXISTS source_processing.corpus_quota (
    singleton boolean PRIMARY KEY DEFAULT true CHECK (singleton),
    total_bytes bigint NOT NULL CHECK (total_bytes >= 0)
);

INSERT INTO source_processing.corpus_quota (singleton, total_bytes)
VALUES (true, 0)
ON CONFLICT (singleton) DO NOTHING;

CREATE TABLE IF NOT EXISTS source_processing.corpus_original_reservations (
    fingerprint char(64) PRIMARY KEY,
    content_length bigint NOT NULL CHECK (content_length > 0),
    reserved_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (fingerprint ~ '^[0-9a-f]{64}$')
);
