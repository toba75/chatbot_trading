-- ADR-053 : expand/contract et rejeu local des contrats historiques M-014.
-- Chaque backfill reste dans le bounded context propriétaire.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

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

UPDATE source_processing.document_conversion_requests AS request
   SET producer_environment = job.environment,
       producer_deployment_id = job.deployment_id,
       producer_configuration_hash = job.configuration_hash
  FROM platform.technical_jobs AS job
 WHERE job.job_id = request.job_id
   AND request.producer_environment IS NULL
   AND request.producer_deployment_id IS NULL
   AND request.producer_configuration_hash IS NULL;

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
        SELECT * INTO STRICT producer
          FROM source_processing.job_outbox
         WHERE outbox_id = NEW.submission_id;
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

ALTER TABLE source_processing.document_conversion_requests
    ALTER COLUMN producer_environment SET NOT NULL,
    ALTER COLUMN producer_deployment_id SET NOT NULL,
    ALTER COLUMN producer_configuration_hash SET NOT NULL,
    ADD CONSTRAINT document_conversion_producer_identity_check CHECK (
        producer_environment IN ('development', 'test', 'production')
        AND producer_deployment_id ~ '^[a-z0-9]+(-[a-z0-9]+)*$'
        AND producer_configuration_hash ~ '^[0-9a-f]{64}$'
    );

-- Le vrai contrat M004 pré-023 est enrichi depuis son message durable. Toute
-- lease de relais ou de worker qui portait l'ancien payload est révoquée.
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
       status = CASE WHEN status = 'running' THEN 'pending' ELSE status END,
       lease_owner = CASE WHEN status = 'running' THEN NULL ELSE lease_owner END,
       lease_expires_at = CASE
           WHEN status = 'running' THEN NULL ELSE lease_expires_at END,
       claim_generation = CASE
           WHEN status = 'running' THEN claim_generation + 1
           ELSE claim_generation END,
       claim_token = CASE WHEN status = 'running' THEN NULL ELSE claim_token END
 WHERE job_name = 'CONVERT_DOCUMENT'
   AND status IN ('pending', 'running')
   AND NOT (payload ? 'orchestration_version');

-- Les projections des writers M005 à trois champs reçoivent d'abord leur
-- identité productrice durable. Le nom de collection est la convention locale
-- qualifiée par le couple environnement/déploiement de ce writer historique.
UPDATE knowledge_access.knowledge_projections AS projection
   SET environment = message.environment,
       deployment_id = message.deployment_id,
       configuration_hash = message.configuration_hash,
       qdrant_collection_name =
           'ostrading-' || message.environment || '-knowledge-access'
  FROM knowledge_access.job_outbox AS message
 WHERE message.job_name = 'PROJECT_DOCUMENT'
   AND (SELECT count(*) FROM jsonb_object_keys(message.payload)) = 3
   AND message.payload ->> 'projection_id' = projection.projection_id
   AND projection.environment IS NULL
   AND projection.deployment_id IS NULL
   AND projection.configuration_hash IS NULL
   AND projection.qdrant_collection_name IS NULL;

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

UPDATE knowledge_access.job_outbox
   SET payload = payload,
       status = CASE WHEN status = 'relaying' THEN 'pending' ELSE status END,
       relay_owner = CASE WHEN status = 'relaying' THEN NULL ELSE relay_owner END,
       relay_lease_expires_at = CASE
           WHEN status = 'relaying' THEN NULL ELSE relay_lease_expires_at END,
       relay_claim_generation = CASE
           WHEN status = 'relaying' THEN relay_claim_generation + 1
           ELSE relay_claim_generation END,
       relay_claim_token = CASE
           WHEN status = 'relaying' THEN NULL ELSE relay_claim_token END
 WHERE job_name = 'PROJECT_DOCUMENT'
   AND NOT (payload ? 'contract_version')
   AND EXISTS (
       SELECT 1
         FROM knowledge_access.canonical_publication_inbox AS publication
        WHERE publication.canonical_version_id =
              knowledge_access.job_outbox.payload ->> 'canonical_version_id'
   );

UPDATE platform.technical_jobs AS job
   SET payload = message.payload,
       execution_contract_name = 'project-canonical-document',
       execution_contract_version = '1.0',
       capacity_capability = 'knowledge-projection',
       capacity_slots = 0,
       capacity_device = NULL,
       storage_environment = job.environment,
       status = CASE WHEN job.status = 'running' THEN 'pending' ELSE job.status END,
       lease_owner = CASE WHEN job.status = 'running' THEN NULL ELSE job.lease_owner END,
       lease_expires_at = CASE
           WHEN job.status = 'running' THEN NULL ELSE job.lease_expires_at END,
       claim_generation = CASE
           WHEN job.status = 'running' THEN job.claim_generation + 1
           ELSE job.claim_generation END,
       claim_token = CASE WHEN job.status = 'running' THEN NULL ELSE job.claim_token END
  FROM knowledge_access.job_outbox AS message
 WHERE job.job_name = 'PROJECT_DOCUMENT'
   AND job.source_message_id = message.outbox_id
   AND job.status IN ('pending', 'running')
   AND NOT (job.payload ? 'contract_version');

-- Les jobs M005 encore privés de publication KA sont drainés : le relais
-- canonique qualifiera ensuite l'outbox, puis le relais platform les réactivera.
UPDATE platform.technical_jobs
   SET status = 'pending', result = NULL, failure_reason = NULL,
       lease_owner = NULL, lease_expires_at = NULL,
       claim_generation = claim_generation + 1, claim_token = NULL,
       source_message_id = NULL, source_message_hash = NULL
 WHERE job_name = 'PROJECT_DOCUMENT'
   AND NOT (payload ? 'contract_version');

-- Une projection historique sans génération redevient un travail explicite.
UPDATE knowledge_access.knowledge_projections AS projection
   SET status = 'REQUESTED', execution_phase = 'QUEUED',
       completed_units = 0, total_units = 1, failure_error_code = NULL,
       aggregate_version = aggregate_version + 1,
       state_observed_at = CURRENT_TIMESTAMP
 WHERE projection.status = 'STALE'
   AND projection.index_generation IS NULL
   AND projection.environment IS NOT NULL
   AND EXISTS (
       SELECT 1
         FROM knowledge_access.job_outbox AS message
        WHERE message.job_name = 'PROJECT_DOCUMENT'
          AND message.payload ->> 'projection_id' = projection.projection_id
   );

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

-- Les publications pré-024 reçoivent une outbox SP. KA sera touché seulement
-- par le relais idempotent, dans une transaction KA ultérieure.
WITH historical AS (
    SELECT version.*, request.producer_environment AS environment,
           request.producer_deployment_id AS deployment_id,
           request.producer_configuration_hash AS configuration_hash,
           request.total_units AS historical_page_count,
           ('EVT-M014-BACKFILL-' || upper(substr(encode(digest(
               version.canonical_version_id, 'sha256'
           ), 'hex'), 1, 40))) AS event_id,
           source.fingerprint AS source_sha256
      FROM source_processing.canonical_source_versions AS version
      JOIN source_processing.source_documents AS source
        ON source.document_id = version.document_id
      JOIN source_processing.document_conversion_requests AS request
        ON request.document_id = version.document_id
     WHERE NOT EXISTS (
         SELECT 1
           FROM source_processing.canonical_publication_outbox AS existing
          WHERE existing.canonical_version_id = version.canonical_version_id
     )
), events AS (
    SELECT historical.*,
           jsonb_build_object(
               'event_id', event_id,
               'event_type', 'CanonicalSourcePublished',
               'event_version', 1,
               'occurred_at', to_char(
                   accepted_at AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'
               ),
               'aggregate_type', 'CanonicalSource',
               'aggregate_id', canonical_source_id,
               'aggregate_version', 1,
               'correlation_id', 'CORR-' || canonical_version_id,
               'causation_id', 'CMD-' || canonical_version_id,
               'producer_context', 'SP',
               'payload', jsonb_build_object(
                   'schema_version', '1.0',
                   'canonical_source_id', canonical_source_id,
                   'document_id', document_id,
                   'canonical_version_id', canonical_version_id,
                   'source_sha256', source_sha256,
                   'canonical_artifact_sha256', canonical_artifact_sha256,
                   'page_count', CASE
                       WHEN canonical_assembly_id IS NOT NULL THEN page_count
                       ELSE historical_page_count
                   END,
                   'accepted_at', to_char(
                       accepted_at AT TIME ZONE 'UTC',
                       'YYYY-MM-DD"T"HH24:MI:SS"Z"'
                   ),
                   'quality_policy_version', CASE
                       WHEN canonical_assembly_id IS NOT NULL
                           THEN quality_policy_version
                       ELSE 'canonical-quality-m004-v1'
                   END
               )
           ) AS event_payload
      FROM historical
)
INSERT INTO source_processing.canonical_publication_outbox (
    event_id, canonical_version_id, canonical_artifact_ref,
    environment, deployment_id, configuration_hash,
    event_payload, event_fingerprint, status, relay_generation
)
SELECT event_id, canonical_version_id, canonical_artifact_ref,
       environment, deployment_id, configuration_hash,
       event_payload,
       encode(digest(source_processing.canonical_jsonb(event_payload),
                     'sha256'), 'hex'),
       'pending', 0
  FROM events;

-- Les triggers restent en phase expand. Leur retrait appartient à une
-- migration contract séparée après drainage vérifié des anciens workers.
