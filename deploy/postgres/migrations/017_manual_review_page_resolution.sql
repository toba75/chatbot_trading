ALTER TABLE source_processing.page_decisions
    ADD COLUMN manual_review_decision text,
    ADD COLUMN manual_route_name text,
    ADD COLUMN manual_reviewer_id text,
    ADD COLUMN manual_review_reason text;

ALTER TABLE source_processing.page_decisions
    ADD CONSTRAINT page_decision_manual_review_resolution_check CHECK (
        (
            manual_review_decision IS NULL
            AND manual_route_name IS NULL
            AND manual_reviewer_id IS NULL
            AND manual_review_reason IS NULL
        )
        OR (
            manual_review_decision = 'CONFIRM_EMPTY'
            AND manual_route_name IS NULL
            AND manual_reviewer_id IS NOT NULL
            AND manual_reviewer_id = btrim(manual_reviewer_id)
            AND manual_reviewer_id <> ''
            AND manual_review_reason IS NOT NULL
            AND manual_review_reason = btrim(manual_review_reason)
            AND manual_review_reason <> ''
        )
        OR (
            manual_review_decision = 'ASSIGN_ROUTE'
            AND manual_route_name IN (
                'NATIVE_STANDARD',
                'SCAN_GRANITE',
                'PREPROCESS_GRANITE',
                'BAD_OCR_TO_GRANITE',
                'MIXED_PAGEWISE',
                'TARGETED_ENRICHMENT'
            )
            AND manual_reviewer_id IS NOT NULL
            AND manual_reviewer_id = btrim(manual_reviewer_id)
            AND manual_reviewer_id <> ''
            AND manual_review_reason IS NOT NULL
            AND manual_review_reason = btrim(manual_review_reason)
            AND manual_review_reason <> ''
        )
    );

-- ADR-041 : reprendre uniquement les revues historiques dont le seul blocage
-- provenait de l'ancienne règle EMPTY -> MANUAL_REVIEW. Une vraie page
-- UNSUPPORTED_OR_CORRUPT reste en revue et n'est jamais routée implicitement.
CREATE TEMPORARY TABLE legacy_empty_route_candidates ON COMMIT DROP AS
SELECT
    d.processing_run_id,
    d.page_number,
    d.page_state,
    CASE
        WHEN d.page_state IN ('NATIVE_OK', 'NATIVE_SUSPECT') THEN 'NATIVE_STANDARD'
        WHEN d.page_state = 'SCAN_CLEAN' THEN 'SCAN_GRANITE'
        WHEN d.page_state = 'SCAN_DEGRADED' THEN 'PREPROCESS_GRANITE'
        WHEN d.page_state = 'OCR_BAD' THEN 'BAD_OCR_TO_GRANITE'
        WHEN d.page_state = 'MIXED_CONTENT' THEN 'MIXED_PAGEWISE'
        WHEN d.page_state = 'COMPLEX_VISUAL' THEN 'TARGETED_ENRICHMENT'
        WHEN d.page_state = 'EMPTY' THEN 'SKIP_EMPTY'
    END AS route_name,
    CASE
        WHEN d.page_state = 'NATIVE_OK' THEN 0.98
        WHEN d.page_state = 'NATIVE_SUSPECT' THEN 0.86
        WHEN d.page_state = 'SCAN_CLEAN' THEN 0.94
        WHEN d.page_state = 'SCAN_DEGRADED' THEN 0.91
        WHEN d.page_state IN ('OCR_BAD', 'MIXED_CONTENT') THEN 0.90
        WHEN d.page_state = 'COMPLEX_VISUAL' THEN 0.86
        WHEN d.page_state = 'EMPTY' THEN 1.00
    END::double precision AS confidence_score,
    CASE
        WHEN d.page_state IN ('NATIVE_SUSPECT', 'COMPLEX_VISUAL') THEN 'BENCHMARK'
        ELSE 'AUTO'
    END AS decision_mode,
    CASE
        WHEN d.page_state = 'SCAN_DEGRADED' THEN 'OCR_PHYSICAL_PREPROCESSING'
        ELSE 'NONE'
    END AS preprocessing_action,
    d.justification AS diagnostic_justification
FROM source_processing.page_decisions AS d
JOIN source_processing.document_processing_runs AS run
  ON run.processing_run_id = d.processing_run_id
WHERE run.status = 'MANUAL_REVIEW'
  AND NOT EXISTS (
      SELECT 1
      FROM source_processing.route_plans AS existing_plan
      WHERE existing_plan.processing_run_id = run.processing_run_id
  )
  AND EXISTS (
      SELECT 1
      FROM source_processing.page_decisions AS empty_decision
      WHERE empty_decision.processing_run_id = run.processing_run_id
        AND empty_decision.page_state = 'EMPTY'
  )
  AND NOT EXISTS (
      SELECT 1
      FROM source_processing.page_decisions AS blocked_decision
      WHERE blocked_decision.processing_run_id = run.processing_run_id
        AND blocked_decision.page_state NOT IN (
            'NATIVE_OK',
            'NATIVE_SUSPECT',
            'SCAN_CLEAN',
            'SCAN_DEGRADED',
            'OCR_BAD',
            'MIXED_CONTENT',
            'COMPLEX_VISUAL',
            'EMPTY'
        )
  );

CREATE TEMPORARY TABLE legacy_empty_route_plans ON COMMIT DROP AS
WITH route_counts AS (
    SELECT processing_run_id, route_name, count(*) AS route_count
    FROM legacy_empty_route_candidates
    WHERE route_name <> 'SKIP_EMPTY'
    GROUP BY processing_run_id, route_name
),
maximum_counts AS (
    SELECT processing_run_id, max(route_count) AS maximum_count
    FROM route_counts
    GROUP BY processing_run_id
),
dominant_routes AS (
    SELECT
        candidate.processing_run_id,
        CASE
            WHEN count(route_counts.route_name) = 1 THEN min(route_counts.route_name)
            ELSE 'MIXED_PAGEWISE'
        END AS dominant_route_name
    FROM (
        SELECT DISTINCT processing_run_id
        FROM legacy_empty_route_candidates
    ) AS candidate
    LEFT JOIN maximum_counts
      ON maximum_counts.processing_run_id = candidate.processing_run_id
    LEFT JOIN route_counts
      ON route_counts.processing_run_id = candidate.processing_run_id
     AND route_counts.route_count = maximum_counts.maximum_count
    GROUP BY candidate.processing_run_id
)
SELECT
    candidate.processing_run_id,
    dominant_routes.dominant_route_name,
    avg(candidate.confidence_score)::double precision AS confidence_score
FROM legacy_empty_route_candidates AS candidate
JOIN dominant_routes
  ON dominant_routes.processing_run_id = candidate.processing_run_id
GROUP BY candidate.processing_run_id, dominant_routes.dominant_route_name;

INSERT INTO source_processing.route_plans (
    processing_run_id,
    routing_policy_version,
    dominant_route_name,
    confidence_score
)
SELECT
    processing_run_id,
    'routing-v1',
    dominant_route_name,
    confidence_score
FROM legacy_empty_route_plans;

INSERT INTO source_processing.page_routes (
    processing_run_id,
    page_number,
    route_name,
    decision_mode,
    confidence_score,
    preprocessing_action,
    routing_policy_version,
    justification,
    is_exception
)
SELECT
    candidate.processing_run_id,
    candidate.page_number,
    candidate.route_name,
    candidate.decision_mode,
    candidate.confidence_score,
    candidate.preprocessing_action,
    'routing-v1',
    candidate.page_state || ' -> ' || candidate.route_name
        || ' par reprise déterministe ADR-041; diagnostic: '
        || candidate.diagnostic_justification,
    candidate.route_name <> route_plan.dominant_route_name
FROM legacy_empty_route_candidates AS candidate
JOIN legacy_empty_route_plans AS route_plan
  ON route_plan.processing_run_id = candidate.processing_run_id;

UPDATE source_processing.document_processing_runs AS run
SET status = 'ROUTE_PLANNED',
    manual_review_reason = NULL,
    blocking_policy_version = NULL
WHERE EXISTS (
    SELECT 1
    FROM legacy_empty_route_plans AS route_plan
    WHERE route_plan.processing_run_id = run.processing_run_id
);
