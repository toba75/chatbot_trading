-- Correctifs de revue M-014 : expand/contract local, rejeu et contrats KA stricts.

-- EXPAND : l'outbox publique transporte l'artefact sans lecture KA de la table
-- privée source_processing.canonical_source_versions. Le trigger maintient la
-- compatibilité de l'ancien writer pendant la fenêtre de rollback locale.
ALTER TABLE source_processing.canonical_publication_outbox
    ADD COLUMN IF NOT EXISTS canonical_artifact_ref text;

CREATE OR REPLACE FUNCTION source_processing.fill_canonical_publication_artifact_ref()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.canonical_artifact_ref IS NULL THEN
        SELECT version.canonical_artifact_ref
          INTO NEW.canonical_artifact_ref
          FROM source_processing.canonical_source_versions AS version
         WHERE version.canonical_version_id = NEW.canonical_version_id;
    END IF;
    IF NEW.canonical_artifact_ref IS NULL THEN
        RAISE EXCEPTION 'CANONICAL_PUBLICATION_ARTIFACT_REF_MISSING';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS canonical_publication_artifact_ref_compatibility
    ON source_processing.canonical_publication_outbox;
CREATE TRIGGER canonical_publication_artifact_ref_compatibility
BEFORE INSERT OR UPDATE OF canonical_version_id, canonical_artifact_ref
ON source_processing.canonical_publication_outbox
FOR EACH ROW
EXECUTE FUNCTION source_processing.fill_canonical_publication_artifact_ref();

UPDATE source_processing.canonical_publication_outbox AS message
   SET canonical_artifact_ref = version.canonical_artifact_ref
  FROM source_processing.canonical_source_versions AS version
 WHERE message.canonical_version_id = version.canonical_version_id
   AND message.canonical_artifact_ref IS NULL;

ALTER TABLE source_processing.canonical_publication_outbox
    ALTER COLUMN canonical_artifact_ref SET NOT NULL;

-- Les publications antérieures à l'inbox KA sont rejouées explicitement. Le
-- relais reste idempotent et l'ACK SP ne précède jamais la transaction KA.
UPDATE source_processing.canonical_publication_outbox AS message
   SET status = 'pending', relayed_at = NULL, relay_owner = NULL,
       relay_lease_until = NULL, relay_token = NULL
 WHERE message.status = 'relayed'
   AND NOT EXISTS (
       SELECT 1
         FROM knowledge_access.canonical_publication_inbox AS inbox
        WHERE inbox.event_id = message.event_id
   );

-- CONTRACT : aucune valeur métier implicite pour la redélivrance.
ALTER TABLE knowledge_access.projection_event_receipts
    ALTER COLUMN delivery_count DROP DEFAULT;

-- Les anciennes projections déclarées SEARCHABLE sans génération vérifiable
-- sont requalifiées explicitement avant validation du contrat.
UPDATE knowledge_access.knowledge_projections
   SET status = 'STALE', execution_phase = 'SUCCEEDED',
       completed_units = total_units, failure_error_code = NULL,
       state_observed_at = CURRENT_TIMESTAMP,
       aggregate_version = aggregate_version + 1
 WHERE status = 'SEARCHABLE'
   AND index_generation IS NULL;

ALTER TABLE knowledge_access.knowledge_projections
    VALIDATE CONSTRAINT knowledge_projections_generation_coherence;

CREATE INDEX IF NOT EXISTS knowledge_projections_latest_publication_idx
    ON knowledge_access.canonical_publication_inbox (
        environment, deployment_id, configuration_hash,
        document_id, received_at DESC, event_id DESC
    );

-- Les jobs PROJECT_DOCUMENT déjà relayés sous le contrat historique 1.0 sont
-- migrés vers les exigences explicites désormais contrôlées par le worker.
ALTER TABLE platform.technical_jobs
    DROP CONSTRAINT IF EXISTS technical_jobs_convert_page_requirements;
ALTER TABLE platform.technical_jobs
    ADD CONSTRAINT technical_jobs_routed_execution_requirements CHECK (
        (
            job_name = 'CONVERT_PAGE'
            AND execution_contract_name = 'CONVERT_PAGE'
            AND execution_contract_version = '1.0'
            AND capacity_capability IS NOT NULL
            AND capacity_slots IS NOT NULL
            AND storage_environment IS NOT NULL
        )
        OR (
            job_name = 'PROJECT_DOCUMENT'
            AND execution_contract_name = 'project-canonical-document'
            AND execution_contract_version = '1.0'
            AND capacity_capability = 'knowledge-projection'
            AND capacity_slots = 0
            AND capacity_device IS NULL
            AND storage_environment = environment
        )
        OR (
            job_name NOT IN ('CONVERT_PAGE', 'PROJECT_DOCUMENT')
            AND execution_contract_name IS NULL
            AND execution_contract_version IS NULL
            AND capacity_capability IS NULL
            AND capacity_slots IS NULL
            AND capacity_device IS NULL
            AND storage_environment IS NULL
        )
    ) NOT VALID;

UPDATE platform.technical_jobs
   SET execution_contract_name = 'project-canonical-document',
       execution_contract_version = '1.0',
       capacity_capability = 'knowledge-projection',
       capacity_slots = 0,
       capacity_device = NULL,
       storage_environment = environment
 WHERE job_name = 'PROJECT_DOCUMENT'
   AND payload ->> 'contract_version' = '1.0'
   AND execution_contract_name IS NULL
   AND execution_contract_version IS NULL
   AND capacity_capability IS NULL
   AND capacity_slots IS NULL
   AND capacity_device IS NULL
   AND storage_environment IS NULL;

ALTER TABLE platform.technical_jobs
    VALIDATE CONSTRAINT technical_jobs_routed_execution_requirements;

-- CONTRACT : abandoned n'a aucun producteur légitime. Les éventuels messages
-- historiques deviennent des échecs explicites, consommables et ACKables.
UPDATE platform.page_completion_outbox
   SET terminal_status = 'failed'
 WHERE terminal_status = 'abandoned';

ALTER TABLE platform.page_completion_outbox
    DROP CONSTRAINT IF EXISTS page_completion_outbox_terminal_status_check,
    DROP CONSTRAINT IF EXISTS page_completion_outbox_check;
ALTER TABLE platform.page_completion_outbox
    ADD CONSTRAINT page_completion_outbox_terminal_status_check
        CHECK (terminal_status IN ('succeeded', 'failed')),
    ADD CONSTRAINT page_completion_outbox_terminal_failure_coherence CHECK (
        (terminal_status = 'succeeded' AND failure_reason IS NULL)
        OR (
            terminal_status = 'failed'
            AND failure_reason IS NOT NULL
            AND btrim(failure_reason) <> ''
            AND failure_reason = btrim(failure_reason)
        )
    );
