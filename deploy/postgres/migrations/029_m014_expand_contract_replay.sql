-- ADR-053 : upgrade historique strict M-014.
-- Chaque bounded context ne réconcilie que ses propres tables. Une valeur
-- opérationnelle absente reste explicitement à qualifier par un opérateur.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- La trace de complétion appartient au contexte platform et provient de son
-- propre job. Aucun agrégat SP ou KA n'est consulté.
ALTER TABLE platform.page_completion_outbox
    ADD COLUMN IF NOT EXISTS trace_id text;

UPDATE platform.page_completion_outbox AS completion
   SET trace_id = job.trace_id
  FROM platform.technical_jobs AS job
 WHERE job.job_id = completion.job_id
   AND completion.trace_id IS NULL;

ALTER TABLE platform.page_completion_outbox
    ALTER COLUMN trace_id SET NOT NULL,
    ADD CONSTRAINT page_completion_trace_id_check CHECK (
        btrim(trace_id) <> '' AND trace_id = btrim(trace_id)
    );

-- L'identité historique du producteur est une donnée d'audit SP. Elle peut
-- rester entièrement inconnue pour les lignes antérieures sans message SP,
-- mais elle n'est jamais complétée depuis la file platform.
ALTER TABLE source_processing.document_conversion_requests
    ADD COLUMN IF NOT EXISTS producer_environment text,
    ADD COLUMN IF NOT EXISTS producer_deployment_id text,
    ADD COLUMN IF NOT EXISTS producer_configuration_hash char(64);

UPDATE source_processing.document_conversion_requests AS request
   SET producer_environment = message.environment,
       producer_deployment_id = message.deployment_id,
       producer_configuration_hash = message.configuration_hash
  FROM source_processing.job_outbox AS message
 WHERE message.outbox_id = request.submission_id
   AND request.producer_environment IS NULL
   AND request.producer_deployment_id IS NULL
   AND request.producer_configuration_hash IS NULL;

ALTER TABLE source_processing.document_conversion_requests
    ADD CONSTRAINT document_conversion_producer_identity_check CHECK (
        (
            producer_environment IS NULL
            AND producer_deployment_id IS NULL
            AND producer_configuration_hash IS NULL
        )
        OR (
            producer_environment IS NOT NULL
            AND producer_deployment_id IS NOT NULL
            AND producer_configuration_hash IS NOT NULL
            AND producer_environment IN ('development', 'test', 'production')
            AND producer_deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            AND producer_configuration_hash ~ '^[0-9a-f]{64}$'
        )
    );

CREATE OR REPLACE FUNCTION source_processing.enrich_m004_conversion_identity()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    producer source_processing.job_outbox%ROWTYPE;
BEGIN
    IF NEW.producer_environment IS NULL
       AND NEW.producer_deployment_id IS NULL
       AND NEW.producer_configuration_hash IS NULL THEN
        SELECT * INTO producer
          FROM source_processing.job_outbox
         WHERE outbox_id = NEW.submission_id;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'CONVERSION_PRODUCER_IDENTITY_UNPROVEN';
        END IF;
        NEW.producer_environment := producer.environment;
        NEW.producer_deployment_id := producer.deployment_id;
        NEW.producer_configuration_hash := producer.configuration_hash;
    ELSIF NEW.producer_environment IS NULL
       OR NEW.producer_deployment_id IS NULL
       OR NEW.producer_configuration_hash IS NULL THEN
        RAISE EXCEPTION 'CONVERSION_PRODUCER_IDENTITY_PARTIAL';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS enrich_m004_conversion_identity_compatibility
    ON source_processing.document_conversion_requests;
CREATE TRIGGER enrich_m004_conversion_identity_compatibility
BEFORE INSERT OR UPDATE OF submission_id
ON source_processing.document_conversion_requests
FOR EACH ROW
EXECUTE FUNCTION source_processing.enrich_m004_conversion_identity();

-- Le message SP et le job platform sont réparés indépendamment à partir de
-- leur payload local. Les deux anciennes leases sont révoquées. Le job garde
-- claim_generation == execution_attempts ; seul un nouveau claim les avance.
UPDATE source_processing.job_outbox
   SET payload = jsonb_set(
           payload, '{orchestration_version}', '"m004-inline-v1"'::jsonb, true
       ),
       status = CASE WHEN status = 'relaying' THEN 'pending' ELSE status END,
       relay_owner = CASE WHEN status = 'relaying' THEN NULL ELSE relay_owner END,
       relay_lease_expires_at = CASE
           WHEN status = 'relaying' THEN NULL ELSE relay_lease_expires_at END,
       relay_claim_generation = CASE
           WHEN status = 'relaying' THEN relay_claim_generation + 1
           ELSE relay_claim_generation END,
       relay_claim_token = CASE
           WHEN status = 'relaying' THEN NULL ELSE relay_claim_token END
 WHERE job_name = 'CONVERT_DOCUMENT'
   AND NOT (payload ? 'orchestration_version');

UPDATE platform.technical_jobs
   SET payload = jsonb_set(
           payload, '{orchestration_version}', '"m004-inline-v1"'::jsonb, true
       ),
       status = 'pending', result = NULL, failure_reason = NULL,
       lease_owner = NULL, lease_expires_at = NULL, claim_token = NULL,
       source_message_id = NULL, source_message_hash = NULL
 WHERE job_name = 'CONVERT_DOCUMENT'
   AND status IN ('pending', 'running')
   AND NOT (payload ? 'orchestration_version');

-- Les anciens messages KA à trois champs sont mis en quarantaine explicite.
-- L'identité de leur producteur est conservée pour audit ; l'identité active
-- du consommateur et le nom Qdrant doivent être fournis séparément.
ALTER TABLE knowledge_access.job_outbox
    DROP CONSTRAINT IF EXISTS job_outbox_status_check,
    DROP CONSTRAINT IF EXISTS knowledge_access_job_outbox_state_coherence;
ALTER TABLE knowledge_access.job_outbox
    ADD CONSTRAINT job_outbox_status_check CHECK (
        status IN (
            'pending', 'relaying', 'relayed', 'failed',
            'reconciliation_required'
        )
    ),
    ADD CONSTRAINT knowledge_access_job_outbox_state_coherence CHECK (
        (status = 'pending'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'relaying'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NOT NULL AND relay_lease_expires_at IS NOT NULL
            AND relay_claim_generation > 0 AND relay_claim_token IS NOT NULL
            AND failure_error_code IS NULL)
        OR (status = 'relayed'
            AND platform_job_id IS NOT NULL AND relayed_at IS NOT NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
        OR (status = 'failed'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL
            AND failure_error_code = 'WORKER_ENVIRONMENT_MISMATCH')
        OR (status = 'reconciliation_required'
            AND platform_job_id IS NULL AND relayed_at IS NULL
            AND relay_owner IS NULL AND relay_lease_expires_at IS NULL
            AND relay_claim_token IS NULL AND failure_error_code IS NULL)
    );

CREATE TABLE knowledge_access.historical_projection_reconciliation (
    projection_id text PRIMARY KEY
        REFERENCES knowledge_access.knowledge_projections(projection_id),
    outbox_id text NOT NULL UNIQUE
        REFERENCES knowledge_access.job_outbox(outbox_id),
    producer_environment text NOT NULL,
    producer_deployment_id text NOT NULL,
    producer_configuration_hash char(64) NOT NULL,
    historical_platform_job_id text,
    qdrant_collection_name text,
    consumer_environment text,
    consumer_deployment_id text,
    consumer_configuration_hash char(64),
    status text NOT NULL CHECK (
        status IN ('reconciliation_required', 'qualified')
    ),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    qualified_at timestamptz,
    CHECK (
        (
            status = 'reconciliation_required'
            AND qdrant_collection_name IS NULL
            AND consumer_environment IS NULL
            AND consumer_deployment_id IS NULL
            AND consumer_configuration_hash IS NULL
            AND qualified_at IS NULL
        )
        OR (
            status = 'qualified'
            AND qdrant_collection_name IS NOT NULL
            AND btrim(qdrant_collection_name) <> ''
            AND qdrant_collection_name = btrim(qdrant_collection_name)
            AND consumer_environment IN ('development', 'test', 'production')
            AND consumer_deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            AND consumer_configuration_hash ~ '^[0-9a-f]{64}$'
            AND qualified_at IS NOT NULL
        )
    )
);

INSERT INTO knowledge_access.historical_projection_reconciliation (
    projection_id, outbox_id,
    producer_environment, producer_deployment_id,
    producer_configuration_hash, historical_platform_job_id,
    status
)
SELECT projection.projection_id, message.outbox_id,
       message.environment, message.deployment_id, message.configuration_hash,
       message.platform_job_id, 'reconciliation_required'
  FROM knowledge_access.job_outbox AS message
  JOIN knowledge_access.knowledge_projections AS projection
    ON projection.projection_id = message.payload ->> 'projection_id'
 WHERE message.job_name = 'PROJECT_DOCUMENT'
   AND (SELECT count(*) FROM jsonb_object_keys(message.payload)) = 3
   AND message.payload ?& ARRAY[
       'projection_id', 'document_id', 'canonical_version_id'
   ];

UPDATE knowledge_access.job_outbox
   SET status = 'reconciliation_required',
       platform_job_id = NULL, relayed_at = NULL,
       relay_owner = NULL, relay_lease_expires_at = NULL,
       relay_claim_generation = CASE
           WHEN status = 'relaying' THEN relay_claim_generation + 1
           ELSE relay_claim_generation END,
       relay_claim_token = NULL, failure_error_code = NULL
 WHERE outbox_id IN (
       SELECT reconciliation.outbox_id
         FROM knowledge_access.historical_projection_reconciliation AS reconciliation
   );

-- Le job platform conserve son source_message_id pour que le relais puisse
-- reconnaître le même message après qualification. Le hash est remplacé dans
-- la transaction platform du relais, jamais par cette migration KA.
UPDATE platform.technical_jobs
   SET status = 'pending', result = NULL, failure_reason = NULL,
       lease_owner = NULL, lease_expires_at = NULL, claim_token = NULL
 WHERE job_name = 'PROJECT_DOCUMENT'
   AND status IN ('pending', 'running')
   AND (SELECT count(*) FROM jsonb_object_keys(payload)) = 3
   AND payload ?& ARRAY[
       'projection_id', 'document_id', 'canonical_version_id'
   ];

CREATE OR REPLACE FUNCTION knowledge_access.enrich_m005_projection_job_payload()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    projection knowledge_access.knowledge_projections%ROWTYPE;
    publication knowledge_access.canonical_publication_inbox%ROWTYPE;
BEGIN
    IF NEW.job_name IS DISTINCT FROM 'PROJECT_DOCUMENT'
       OR NEW.payload ? 'contract_version' THEN
        RETURN NEW;
    END IF;
    IF (SELECT count(*) FROM jsonb_object_keys(NEW.payload)) <> 3
       OR NOT (NEW.payload ?& ARRAY[
           'projection_id', 'document_id', 'canonical_version_id'
       ]) THEN
        RAISE EXCEPTION 'PROJECTION_HISTORICAL_PAYLOAD_UNQUALIFIED';
    END IF;

    SELECT * INTO STRICT projection
      FROM knowledge_access.knowledge_projections
     WHERE projection_id = NEW.payload ->> 'projection_id';
    SELECT * INTO STRICT publication
      FROM knowledge_access.canonical_publication_inbox
     WHERE canonical_version_id = NEW.payload ->> 'canonical_version_id';
    IF projection.document_id IS DISTINCT FROM NEW.payload ->> 'document_id'
       OR projection.canonical_version_id IS DISTINCT FROM
          NEW.payload ->> 'canonical_version_id'
       OR projection.environment IS NULL
       OR projection.deployment_id IS NULL
       OR projection.configuration_hash IS NULL
       OR projection.qdrant_collection_name IS NULL THEN
        RAISE EXCEPTION 'PROJECTION_HISTORICAL_PAYLOAD_DIVERGENT';
    END IF;

    NEW.payload := NEW.payload || jsonb_build_object(
        'contract_version', '1.0',
        'canonical_artifact_ref', publication.canonical_artifact_ref,
        'canonical_artifact_sha256', publication.canonical_artifact_sha256,
        'build_fingerprint', projection.build_fingerprint,
        'projection_profile', jsonb_build_object(
            'projection_profile_id', projection.projection_profile_id,
            'chunking_profile', projection.chunking_profile,
            'embedding_model', projection.embedding_model,
            'sparse_profile', projection.sparse_profile,
            'index_schema', projection.index_schema
        ),
        'qdrant_collection_name', projection.qdrant_collection_name,
        'environment_identity', jsonb_build_object(
            'environment', projection.environment,
            'deployment_id', projection.deployment_id,
            'configuration_hash', projection.configuration_hash
        ),
        'causation_event_id', publication.event_id
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS enrich_m005_projection_job_payload_compatibility
    ON knowledge_access.job_outbox;
CREATE TRIGGER enrich_m005_projection_job_payload_compatibility
BEFORE INSERT OR UPDATE OF payload ON knowledge_access.job_outbox
FOR EACH ROW
WHEN (
    NEW.job_name = 'PROJECT_DOCUMENT'
    AND NOT (NEW.payload ? 'contract_version')
)
EXECUTE FUNCTION knowledge_access.enrich_m005_projection_job_payload();

CREATE OR REPLACE FUNCTION knowledge_access.qualify_historical_projection(
    requested_projection_id text,
    requested_qdrant_collection_name text,
    requested_consumer_environment text,
    requested_consumer_deployment_id text,
    requested_consumer_configuration_hash char(64)
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    reconciliation knowledge_access.historical_projection_reconciliation%ROWTYPE;
BEGIN
    SELECT * INTO STRICT reconciliation
      FROM knowledge_access.historical_projection_reconciliation
     WHERE projection_id = requested_projection_id
       AND status = 'reconciliation_required'
     FOR UPDATE;
    IF requested_qdrant_collection_name IS NULL
       OR btrim(requested_qdrant_collection_name) = ''
       OR requested_qdrant_collection_name <> btrim(requested_qdrant_collection_name)
       OR requested_consumer_environment NOT IN (
           'development', 'test', 'production'
       )
       OR requested_consumer_deployment_id !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
       OR requested_consumer_configuration_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'HISTORICAL_PROJECTION_QUALIFICATION_INVALID';
    END IF;

    UPDATE knowledge_access.knowledge_projections
       SET environment = requested_consumer_environment,
           deployment_id = requested_consumer_deployment_id,
           configuration_hash = requested_consumer_configuration_hash,
           qdrant_collection_name = requested_qdrant_collection_name,
           status = 'REQUESTED', execution_phase = 'QUEUED',
           completed_units = 0, total_units = 1, failure_error_code = NULL,
           aggregate_version = aggregate_version + 1,
           state_observed_at = CURRENT_TIMESTAMP
     WHERE projection_id = requested_projection_id;

    UPDATE knowledge_access.job_outbox
       SET environment = requested_consumer_environment,
           deployment_id = requested_consumer_deployment_id,
           configuration_hash = requested_consumer_configuration_hash,
           payload = payload, status = 'pending'
     WHERE outbox_id = reconciliation.outbox_id
       AND status = 'reconciliation_required';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'HISTORICAL_PROJECTION_OUTBOX_NOT_QUALIFIED';
    END IF;

    UPDATE knowledge_access.historical_projection_reconciliation
       SET qdrant_collection_name = requested_qdrant_collection_name,
           consumer_environment = requested_consumer_environment,
           consumer_deployment_id = requested_consumer_deployment_id,
           consumer_configuration_hash = requested_consumer_configuration_hash,
           status = 'qualified', qualified_at = CURRENT_TIMESTAMP
     WHERE projection_id = requested_projection_id;
END;
$$;

-- Sérialisation JSON canonique identique à sort_keys=True/separators(',', ':').
CREATE OR REPLACE FUNCTION source_processing.canonical_jsonb(value jsonb)
RETURNS text
LANGUAGE sql
IMMUTABLE
STRICT
AS $$
SELECT CASE jsonb_typeof(value)
    WHEN 'object' THEN '{' || COALESCE((
        SELECT string_agg(
            to_json(item.key)::text || ':' ||
            source_processing.canonical_jsonb(item.value),
            ',' ORDER BY item.key
        )
          FROM jsonb_each(value) AS item
    ), '') || '}'
    WHEN 'array' THEN '[' || COALESCE((
        SELECT string_agg(
            source_processing.canonical_jsonb(item.value),
            ',' ORDER BY item.ordinality
        )
          FROM jsonb_array_elements(value) WITH ORDINALITY AS item(value, ordinality)
    ), '') || ']'
    ELSE value::text
END
$$;

CREATE TABLE source_processing.historical_canonical_reconciliation (
    canonical_version_id text PRIMARY KEY
        REFERENCES source_processing.canonical_source_versions(canonical_version_id),
    producer_environment text,
    producer_deployment_id text,
    producer_configuration_hash char(64),
    quality_policy_version text,
    consumer_environment text,
    consumer_deployment_id text,
    consumer_configuration_hash char(64),
    status text NOT NULL CHECK (
        status IN ('reconciliation_required', 'qualified')
    ),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    qualified_at timestamptz,
    CHECK (
        (
            producer_environment IS NULL
            AND producer_deployment_id IS NULL
            AND producer_configuration_hash IS NULL
        )
        OR (
            producer_environment IS NOT NULL
            AND producer_deployment_id IS NOT NULL
            AND producer_configuration_hash IS NOT NULL
            AND producer_environment IN ('development', 'test', 'production')
            AND producer_deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            AND producer_configuration_hash ~ '^[0-9a-f]{64}$'
        )
    ),
    CHECK (
        (
            status = 'reconciliation_required'
            AND consumer_environment IS NULL
            AND consumer_deployment_id IS NULL
            AND consumer_configuration_hash IS NULL
            AND qualified_at IS NULL
        )
        OR (
            status = 'qualified'
            AND producer_environment IS NOT NULL
            AND producer_deployment_id IS NOT NULL
            AND producer_configuration_hash IS NOT NULL
            AND quality_policy_version IS NOT NULL
            AND btrim(quality_policy_version) <> ''
            AND quality_policy_version = btrim(quality_policy_version)
            AND consumer_environment IN ('development', 'test', 'production')
            AND consumer_deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
            AND consumer_configuration_hash ~ '^[0-9a-f]{64}$'
            AND qualified_at IS NOT NULL
        )
    )
);

INSERT INTO source_processing.historical_canonical_reconciliation (
    canonical_version_id,
    producer_environment, producer_deployment_id,
    producer_configuration_hash, quality_policy_version, status
)
SELECT version.canonical_version_id,
       request.producer_environment, request.producer_deployment_id,
       request.producer_configuration_hash, version.quality_policy_version,
       'reconciliation_required'
  FROM source_processing.canonical_source_versions AS version
  JOIN source_processing.document_conversion_requests AS request
    ON request.document_id = version.document_id
 WHERE NOT EXISTS (
       SELECT 1
         FROM source_processing.canonical_publication_outbox AS publication
        WHERE publication.canonical_version_id = version.canonical_version_id
   );

CREATE OR REPLACE FUNCTION source_processing.qualify_historical_canonical_publication(
    requested_canonical_version_id text,
    requested_producer_environment text,
    requested_producer_deployment_id text,
    requested_producer_configuration_hash char(64),
    requested_quality_policy_version text,
    requested_consumer_environment text,
    requested_consumer_deployment_id text,
    requested_consumer_configuration_hash char(64)
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    reconciliation source_processing.historical_canonical_reconciliation%ROWTYPE;
    version source_processing.canonical_source_versions%ROWTYPE;
    source source_processing.source_documents%ROWTYPE;
    request source_processing.document_conversion_requests%ROWTYPE;
    generated_event_id text;
    generated_event jsonb;
BEGIN
    SELECT * INTO STRICT reconciliation
      FROM source_processing.historical_canonical_reconciliation
     WHERE canonical_version_id = requested_canonical_version_id
       AND status = 'reconciliation_required'
     FOR UPDATE;
    IF requested_quality_policy_version IS NULL
       OR btrim(requested_quality_policy_version) = ''
       OR requested_quality_policy_version <>
          btrim(requested_quality_policy_version)
       OR requested_consumer_environment NOT IN (
           'development', 'test', 'production'
       )
       OR requested_consumer_deployment_id !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
       OR requested_consumer_configuration_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'HISTORICAL_CANONICAL_QUALIFICATION_INVALID';
    END IF;
    IF requested_producer_environment NOT IN (
           'development', 'test', 'production'
       )
       OR requested_producer_deployment_id !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
       OR requested_producer_configuration_hash !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'HISTORICAL_CANONICAL_PRODUCER_IDENTITY_INVALID';
    END IF;
    IF reconciliation.producer_environment IS NOT NULL
       AND (
           reconciliation.producer_environment IS DISTINCT FROM
               requested_producer_environment
           OR reconciliation.producer_deployment_id IS DISTINCT FROM
               requested_producer_deployment_id
           OR reconciliation.producer_configuration_hash IS DISTINCT FROM
               requested_producer_configuration_hash
       ) THEN
        RAISE EXCEPTION 'HISTORICAL_CANONICAL_PRODUCER_IDENTITY_CONFLICT';
    END IF;
    IF reconciliation.quality_policy_version IS NOT NULL
       AND reconciliation.quality_policy_version IS DISTINCT FROM
           requested_quality_policy_version THEN
        RAISE EXCEPTION 'HISTORICAL_CANONICAL_QUALITY_POLICY_CONFLICT';
    END IF;

    SELECT * INTO STRICT version
      FROM source_processing.canonical_source_versions
     WHERE canonical_version_id = requested_canonical_version_id;
    SELECT * INTO STRICT source
      FROM source_processing.source_documents
     WHERE document_id = version.document_id;
    SELECT * INTO STRICT request
      FROM source_processing.document_conversion_requests
     WHERE document_id = version.document_id;

    generated_event_id := 'EVT-M014-RECONCILED-' || upper(substr(encode(digest(
        version.canonical_version_id, 'sha256'
    ), 'hex'), 1, 40));
    generated_event := jsonb_build_object(
        'event_id', generated_event_id,
        'event_type', 'CanonicalSourcePublished',
        'event_version', 1,
        'occurred_at', to_char(
            version.accepted_at AT TIME ZONE 'UTC',
            'YYYY-MM-DD"T"HH24:MI:SS"Z"'
        ),
        'aggregate_type', 'CanonicalSource',
        'aggregate_id', version.canonical_source_id,
        'aggregate_version', 1,
        'correlation_id', 'CORR-' || version.canonical_version_id,
        'causation_id', 'CMD-' || version.canonical_version_id,
        'producer_context', 'SP',
        'payload', jsonb_build_object(
            'schema_version', '1.0',
            'canonical_source_id', version.canonical_source_id,
            'document_id', version.document_id,
            'canonical_version_id', version.canonical_version_id,
            'source_sha256', source.fingerprint,
            'canonical_artifact_sha256', version.canonical_artifact_sha256,
            'page_count', COALESCE(version.page_count, request.total_units),
            'accepted_at', to_char(
                version.accepted_at AT TIME ZONE 'UTC',
                'YYYY-MM-DD"T"HH24:MI:SS"Z"'
            ),
            'quality_policy_version', requested_quality_policy_version
        )
    );

    INSERT INTO source_processing.canonical_publication_outbox (
        event_id, canonical_version_id, canonical_artifact_ref,
        environment, deployment_id, configuration_hash,
        event_payload, event_fingerprint, status, relay_generation
    ) VALUES (
        generated_event_id, version.canonical_version_id,
        version.canonical_artifact_ref,
        requested_consumer_environment, requested_consumer_deployment_id,
        requested_consumer_configuration_hash, generated_event,
        encode(digest(source_processing.canonical_jsonb(generated_event),
                      'sha256'), 'hex'),
        'pending', 0
    );

    UPDATE source_processing.historical_canonical_reconciliation
       SET producer_environment = requested_producer_environment,
           producer_deployment_id = requested_producer_deployment_id,
           producer_configuration_hash = requested_producer_configuration_hash,
           quality_policy_version = requested_quality_policy_version,
           consumer_environment = requested_consumer_environment,
           consumer_deployment_id = requested_consumer_deployment_id,
           consumer_configuration_hash = requested_consumer_configuration_hash,
           status = 'qualified', qualified_at = CURRENT_TIMESTAMP
     WHERE canonical_version_id = requested_canonical_version_id;
END;
$$;

-- Les triggers restent en phase expand. Leur retrait appartient à une
-- migration contract distincte après drainage vérifié des anciens writers.
