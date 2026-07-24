-- Clôture de revue M14 : coexistence bornée M004/M014 et invariant d'artefact.

-- EXPAND transitoire : un writer M004 antérieur ne connaît pas la colonne 023.
-- Il est reconnu uniquement par son propre message CONVERT_DOCUMENT déjà
-- persisté, dont le payload ne porte pas orchestration_version. Toute absence
-- non prouvée est terminale ; il n'existe aucun DEFAULT SQL permanent.
CREATE OR REPLACE FUNCTION source_processing.classify_m004_inline_orchestration()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    producer_job_name text;
    producer_has_orchestration_version boolean;
BEGIN
    IF NEW.orchestration_version IS NOT NULL THEN
        RETURN NEW;
    END IF;

    SELECT message.job_name, message.payload ? 'orchestration_version'
      INTO producer_job_name, producer_has_orchestration_version
      FROM source_processing.job_outbox AS message
     WHERE message.outbox_id = NEW.submission_id;

    IF producer_job_name IS DISTINCT FROM 'CONVERT_DOCUMENT'
       OR producer_has_orchestration_version IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'M014_ORCHESTRATION_VERSION_REQUIRED';
    END IF;

    NEW.orchestration_version := 'm004-inline-v1';
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS classify_m004_inline_orchestration_compatibility
    ON source_processing.document_conversion_requests;
CREATE TRIGGER classify_m004_inline_orchestration_compatibility
BEFORE INSERT ON source_processing.document_conversion_requests
FOR EACH ROW
WHEN (NEW.orchestration_version IS NULL)
EXECUTE FUNCTION source_processing.classify_m004_inline_orchestration();

-- CONTRACT : les commandes d'assemblage non exécutées doivent attendre la
-- référence de l'artefact canonique réellement publié, et non un fichier
-- candidat local qui n'est jamais rendu public.
UPDATE source_processing.job_outbox
   SET payload = jsonb_set(
       payload,
       '{expected_canonical_artifact}',
       to_jsonb(
           'artifact:source_processing.canonical_sources/CSRC-'
           || substr(payload ->> 'document_id', 5)
           || '/CVER-M014-'
           || upper(left(payload ->> 'idempotence_key', 24))
           || '/docling.json'
       ),
       false
   ),
       status = 'pending', relay_owner = NULL,
       relay_lease_expires_at = NULL,
       relay_claim_generation = relay_claim_generation + 1,
       relay_claim_token = NULL
 WHERE job_name = 'ASSEMBLE_CANONICAL_DOCUMENT'
   AND status <> 'relayed'
   AND jsonb_typeof(payload -> 'expected_canonical_artifact') = 'object';

UPDATE platform.technical_jobs
   SET payload = jsonb_set(
       payload,
       '{expected_canonical_artifact}',
       to_jsonb(
           'artifact:source_processing.canonical_sources/CSRC-'
           || substr(payload ->> 'document_id', 5)
           || '/CVER-M014-'
           || upper(left(payload ->> 'idempotence_key', 24))
           || '/docling.json'
       ),
       false
   )
 WHERE job_name = 'ASSEMBLE_CANONICAL_DOCUMENT'
   AND status IN ('pending', 'running')
   AND jsonb_typeof(payload -> 'expected_canonical_artifact') = 'object';

-- La suppression du trigger constitue une future étape CONTRACT distincte,
-- seulement après preuve qu'aucun writer M004 antérieur ne reste déployable.
