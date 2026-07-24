-- M14 revue : l'identité complète d'environnement suit chaque complétion de page.

ALTER TABLE platform.page_completion_outbox
    ADD COLUMN configuration_hash char(64);

UPDATE platform.page_completion_outbox AS completion
   SET configuration_hash = job.configuration_hash
  FROM platform.technical_jobs AS job
 WHERE job.job_id = completion.job_id;

ALTER TABLE platform.page_completion_outbox
    ALTER COLUMN configuration_hash SET NOT NULL,
    ADD CONSTRAINT page_completion_configuration_hash_format CHECK (
        configuration_hash ~ '^[0-9a-f]{64}$'
    );

CREATE INDEX page_completion_outbox_identity_claim_idx
    ON platform.page_completion_outbox (
        environment,
        deployment_id,
        configuration_hash,
        status,
        relay_lease_until,
        sequence
    );
