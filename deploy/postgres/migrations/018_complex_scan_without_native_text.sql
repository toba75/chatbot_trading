-- ADR-043 : une page sans texte natif dont le scan est propre reste une page
-- SCAN_CLEAN, même si sa mise en page est complexe. TARGETED_ENRICHMENT exige
-- un candidat natif et ne peut donc pas traiter cette combinaison de signaux.
CREATE TEMPORARY TABLE complex_clean_scans ON COMMIT DROP AS
SELECT
    decision.processing_run_id,
    decision.page_number,
    decision.justification AS diagnostic_justification,
    page_route.route_name AS existing_route_name
FROM source_processing.page_decisions AS decision
LEFT JOIN source_processing.page_routes AS page_route
  ON page_route.processing_run_id = decision.processing_run_id
 AND page_route.page_number = decision.page_number
WHERE decision.page_state = 'COMPLEX_VISUAL'
  AND decision.native_text_state = 'ABSENT'
  AND decision.image_state = 'SCAN_CLEAN'
  AND decision.existing_ocr_state = 'NONE';

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM complex_clean_scans
        WHERE existing_route_name IS NOT NULL
          AND existing_route_name <> 'TARGETED_ENRICHMENT'
    ) THEN
        RAISE EXCEPTION
            'ADR-043 refuse de migrer une route inattendue pour un scan complexe sans texte natif';
    END IF;
END
$$;

UPDATE source_processing.page_decisions AS decision
SET page_state = 'SCAN_CLEAN'
FROM complex_clean_scans AS affected
WHERE decision.processing_run_id = affected.processing_run_id
  AND decision.page_number = affected.page_number;

UPDATE source_processing.page_routes AS page_route
SET route_name = 'SCAN_GRANITE',
    decision_mode = 'AUTO',
    confidence_score = 0.94,
    preprocessing_action = 'NONE',
    justification = 'SCAN_CLEAN -> SCAN_GRANITE par migration ADR-043; diagnostic: '
        || affected.diagnostic_justification
FROM complex_clean_scans AS affected
WHERE page_route.processing_run_id = affected.processing_run_id
  AND page_route.page_number = affected.page_number
  AND affected.existing_route_name = 'TARGETED_ENRICHMENT';

CREATE TEMPORARY TABLE complex_scan_routed_runs ON COMMIT DROP AS
SELECT DISTINCT processing_run_id
FROM complex_clean_scans
WHERE existing_route_name = 'TARGETED_ENRICHMENT';

CREATE TEMPORARY TABLE recalculated_route_plans ON COMMIT DROP AS
WITH route_counts AS (
    SELECT route.processing_run_id, route.route_name, count(*) AS route_count
    FROM source_processing.page_routes AS route
    JOIN complex_scan_routed_runs AS affected
      ON affected.processing_run_id = route.processing_run_id
    WHERE route.route_name <> 'SKIP_EMPTY'
    GROUP BY route.processing_run_id, route.route_name
),
maximum_counts AS (
    SELECT processing_run_id, max(route_count) AS maximum_count
    FROM route_counts
    GROUP BY processing_run_id
),
dominant_routes AS (
    SELECT
        maximum_counts.processing_run_id,
        CASE
            WHEN count(route_counts.route_name) = 1 THEN min(route_counts.route_name)
            ELSE 'MIXED_PAGEWISE'
        END AS dominant_route_name
    FROM maximum_counts
    JOIN route_counts
      ON route_counts.processing_run_id = maximum_counts.processing_run_id
     AND route_counts.route_count = maximum_counts.maximum_count
    GROUP BY maximum_counts.processing_run_id
)
SELECT
    dominant_routes.processing_run_id,
    dominant_routes.dominant_route_name,
    avg(page_route.confidence_score)::double precision AS confidence_score
FROM dominant_routes
JOIN source_processing.page_routes AS page_route
  ON page_route.processing_run_id = dominant_routes.processing_run_id
GROUP BY dominant_routes.processing_run_id, dominant_routes.dominant_route_name;

UPDATE source_processing.route_plans AS route_plan
SET dominant_route_name = recalculated.dominant_route_name,
    confidence_score = recalculated.confidence_score
FROM recalculated_route_plans AS recalculated
WHERE route_plan.processing_run_id = recalculated.processing_run_id;

UPDATE source_processing.page_routes AS page_route
SET is_exception = page_route.route_name <> recalculated.dominant_route_name
FROM recalculated_route_plans AS recalculated
WHERE page_route.processing_run_id = recalculated.processing_run_id;
