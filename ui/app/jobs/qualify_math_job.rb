require "digest"
require "json"
require "stringio"

class QualifyMathJob < ApplicationJob
  RESULT_ARTIFACTS = [
    [ :analyzer_response, :raw_response, "response.ndjson", "application/x-ndjson", true ],
    [ :source_evidence, :evidence, "evidence.ndjson.gz", "application/gzip", true ],
    [ :report, :report_bytes, "report.json", "application/json", true ],
    [ :corrections, :corrections, "corrections.json", "application/json", true ],
    [ :correction_evidence, :correction_evidence, "correction-evidence.zip", "application/zip", true ],
    [ :derived_docling_document, :derived_docling_document, "derived-document.json", "application/json", false ],
    [ :derived_html, :derived_html, "derived.html", "text/html", false ],
    [ :derived_markdown, :derived_markdown, "derived.md", "text/markdown", false ],
    [ :native_page_html, :native_page_html, "native-page.html", "text/html", true ]
  ].freeze

  class InvalidState < StandardError; end
  class InterruptedExecution < StandardError; end

  queue_as :math_qualifications
  self.enqueue_after_transaction_commit = false

  def perform(qualification)
    return unless begin_qualification!(qualification)
    result = open_inputs(qualification) do |source, document|
      math_qualification_client.qualify(
        source_file: source,
        source_filename: qualification.conversion_attempt.document.source_pdf.filename.to_s,
        document_file: document,
        source_sha256: qualification.source_sha256,
        docling_document_sha256: qualification.docling_document_sha256
      ) { |event| persist_progress!(qualification, event) }
    end
    persist_result!(qualification, result)
  rescue InvalidState, InterruptedExecution
    raise
  rescue MathQualificationClient::QualificationError => error
    persist_failure!(qualification, error)
    raise
  rescue StandardError => error
    persist_failure!(
      qualification,
      MathQualificationClient::QualificationError.new("unexpected_error", error.message)
    )
    raise
  end

  private

  def begin_qualification!(qualification)
    interrupted = false
    started = false
    qualification.with_lock do
      if qualification.queued? && !qualification.current_contract?
        qualification.update!(
          status: "failed",
          error_code: "obsolete_contract",
          error_message: "Cette qualification historique doit être recréée avec le contrat courant.",
          completed_at: Time.current
        )
      elsif qualification.queued?
        qualification.update!(
          status: "running",
          phase: "source_analysis",
          completed_units: 0,
          total_units: 1,
          started_at: Time.current,
          execution_job_id: job_id
        )
        started = true
      elsif qualification.running? && qualification.execution_job_id == job_id
        qualification.update!(
          status: "failed",
          error_code: "interrupted_execution",
          error_message: "Le processus de qualification s'est arrêté avant de produire un résultat.",
          completed_at: Time.current
        )
        interrupted = true
      else
        raise InvalidState, "La qualification #{qualification.id} n'est plus en attente."
      end
    end
    return started unless interrupted

    raise InterruptedExecution, "La qualification #{qualification.id} interrompue a été rendue terminale."
  end

  def math_qualification_client
    MathQualificationClient.new
  end

  def open_inputs(qualification)
    qualification.conversion_attempt.document.source_pdf.open do |source|
      qualification.conversion_attempt.docling_document.open do |document|
        yield source, document
      end
    end
  end

  def persist_progress!(qualification, event)
    qualification.with_lock do
      ensure_active!(qualification)
      qualification.update!(
        status: "running",
        phase: event.fetch("phase"),
        completed_units: event.fetch("completed_units"),
        total_units: event.fetch("total_units")
      )
    end
  end

  def persist_result!(qualification, result)
    summary, verdict = summarize(result.report, qualification, result)
    qualification.with_lock do
      ensure_active!(qualification)
      qualification.update!(
        phase: "persisting_result",
        completed_units: 0,
        total_units: 1
      )
      attach_result(qualification, result)
      qualification.update!(
        status: "succeeded",
        verdict: verdict,
        summary: summary,
        completed_units: 1,
        completed_at: Time.current
      )
    end
  end

  def summarize(report, qualification, result)
    validate_contract!(report["contract"], qualification, result)
    validate_native_page_html!(report["native_page_html"], result)
    overall = report.dig("alignment", "evaluation", "overall")
    invalid_report!(result) unless overall.is_a?(Hash)
    regions = overall["regions"]
    verdicts = overall["verdicts"]
    invalid_report!(result) unless regions.is_a?(Integer) && verdicts.is_a?(Hash)
    counts = %w[conformant_within_scope contradicted non_verifiable].to_h do |name|
      count = verdicts[name]
      invalid_report!(result) unless count.is_a?(Integer) && count >= 0
      [ name, count ]
    end
    invalid_report!(result) unless counts.values.sum == regions
    coverage = report["coverage"]
    regions_detail = report.dig("alignment", "pdf_source_math_regions")
    pages = report["pages"]
    invalid_report!(result) unless coverage.is_a?(Hash) && regions_detail.is_a?(Array) && pages.is_a?(Array)
    invalid_report!(result) unless regions_detail.size == regions
    summary = {
      "regions" => regions,
      "conformant" => counts.fetch("conformant_within_scope"),
      "contradicted" => counts.fetch("contradicted"),
      "non_verifiable" => counts.fetch("non_verifiable"),
      "coverage" => %w[
        pages_total pages_traced pages_traced_with_exclusions pages_partially_traced
        pages_unsupported pages_ambiguous
      ].to_h do |name|
        value = coverage[name]
        invalid_report!(result) unless value.is_a?(Integer) && value >= 0
        [ name, value ]
      end,
      "region_details" => regions_detail.map { |region| region_summary(region, result) },
      "page_exclusions" => pages.filter_map { |page| page_exclusion(page, result) }
    }
    target_region_ids = regions_detail.filter_map do |region|
      region["region_id"] if region["verdict"] == "contradicted"
    end
    summary["correction"] = correction_summary(
      report["correction"],
      result,
      target_region_ids: target_region_ids,
      native_document: qualification.conversion_attempt.docling_document.download
    )
    invalid_report!(result) unless summary.dig("correction", "targets") == summary.fetch("contradicted")
    invalid_report!(result) unless summary.dig("coverage", "pages_total") == pages.size
    page_statuses = {
      "traced" => "pages_traced",
      "traced_with_exclusions" => "pages_traced_with_exclusions",
      "partially_traced" => "pages_partially_traced",
      "unsupported" => "pages_unsupported",
      "ambiguous" => "pages_ambiguous"
    }
    invalid_report!(result) unless pages.all? do |page|
      page.is_a?(Hash) && page["page"].is_a?(Integer) && page_statuses.key?(page["status"])
    end
    actual_page_counts = pages.map { |page| page_statuses.fetch(page.fetch("status")) }.tally
    invalid_report!(result) unless page_statuses.values.all? do |coverage_key|
      summary.dig("coverage", coverage_key) == actual_page_counts.fetch(coverage_key, 0)
    end
    detail_counts = summary.fetch("region_details").map { |region| region.fetch("verdict") }.tally
    invalid_report!(result) unless counts.all? { |verdict, count| detail_counts.fetch(verdict, 0) == count }
    [ summary, aggregate_verdict(summary) ]
  end

  def validate_contract!(contract, qualification, result)
    expected = {
      "version" => qualification.contract_version,
      "analyzer_version" => qualification.analyzer_version,
      "capability_profile" => qualification.capability_profile,
      "source_sha256" => qualification.source_sha256,
      "docling_document_sha256" => qualification.docling_document_sha256
    }
    invalid_report!(result) unless contract == expected
  end

  def validate_native_page_html!(metadata, result)
    valid = metadata.is_a?(Hash) &&
      metadata["bytes"] == result.native_page_html.bytesize &&
      metadata["sha256"] == Digest::SHA256.hexdigest(result.native_page_html)
    invalid_report!(result) unless valid
  end

  def region_summary(region, result)
    values = region.values_at("region_id", "page", "bbox", "verdict", "semantic_reasons")
    invalid_report!(result) unless values[0].is_a?(String) && values[1].is_a?(Integer) &&
      values[2].is_a?(Array) && values[3].is_a?(String) && values[4].is_a?(Array)
    link_status = region["candidate_link_status"]
    charspan = region["candidate_charspan"]
    invalid_report!(result) unless %w[linked not_linked].include?(link_status)
    invalid_report!(result) unless charspan.nil? ||
      (charspan.is_a?(Array) && charspan.size == 2 && charspan.all?(Integer))
    {
      "id" => values[0],
      "page" => values[1],
      "source_bbox" => values[2],
      "source_text" => region["source_glyph_text"],
      "source_tokens" => region["source_canonical_tokens"],
      "docling_ref" => region["docling_ref"],
      "docling_charspan" => charspan,
      "docling_text" => region["candidate_text"],
      "link_status" => link_status,
      "link_method" => region["candidate_alignment_method"],
      "link_reason" => region["candidate_link_reason"],
      "verdict" => values[3],
      "reasons" => values[4]
    }
  end

  def page_exclusion(page, result)
    if page["status"] == "traced"
      invalid_report!(result) if page.fetch("opaque_regions", []).any?
      return
    end

    if page["status"] == "traced_with_exclusions"
      regions = page["opaque_regions"]
      invalid_report!(result) unless regions.is_a?(Array) && regions.any?
      invalid_report!(result) unless regions.all? do |region|
        bbox = region["bbox"]
        reason = region["reason"]
        %w[form_xobject image_xobject].include?(region["kind"]) &&
          region["resource"].is_a?(String) &&
          region["resource"].present? && bbox.is_a?(Array) && bbox.size == 4 &&
          bbox.all? { |coordinate| coordinate.is_a?(Numeric) && coordinate.finite? } &&
          bbox[0] < bbox[2] && bbox[1] < bbox[3] && reason.is_a?(Hash) &&
          reason["code"].is_a?(String) && reason["code"].present? &&
          reason["message"].is_a?(String) && reason["message"].present?
      end
      reasons = regions.map { |region| region["reason"] }.uniq
      return {
        "page" => page["page"], "status" => page["status"],
        "reasons" => reasons,
        "regions" => regions.map { |region| region.slice("kind", "resource", "bbox") }
      }
    end

    invalid_report!(result) unless page["page"].is_a?(Integer) && page["reasons"].is_a?(Array)
    { "page" => page["page"], "status" => page["status"], "reasons" => page["reasons"] }
  end

  def aggregate_verdict(summary)
    return "contradicted" if summary.fetch("contradicted").positive?
    return "non_verifiable" if summary.fetch("regions").zero?
    return "non_verifiable" if summary.fetch("non_verifiable") == summary.fetch("regions")
    return "partial" if summary.fetch("non_verifiable").positive?

    "conformant_within_scope"
  end

  def correction_summary(correction, result, target_region_ids:, native_document:)
    MathCorrectionResultValidator.new(
      result,
      native_document: native_document
    ).validate(
      correction, target_region_ids: target_region_ids
    )
  rescue MathCorrectionResultValidator::InvalidResult
    invalid_report!(result)
  end

  def invalid_report!(result)
    raise MathQualificationClient::QualificationError.new(
      "invalid_report",
      "Le rapport de qualification mathématique est invalide.",
      result: result
    )
  end

  def attach_result(qualification, result)
    attach_artifacts(qualification, result, partial: false)
  end

  def attach(attachment, content, filename, content_type)
    attachment.attach(io: StringIO.new(content), filename: filename, content_type: content_type)
  end

  def persist_failure!(qualification, error)
    qualification.with_lock do
      return unless active?(qualification)

      attach_partial(qualification, error.result) if error.result
      qualification.update!(
        status: "failed",
        error_code: error.code,
        error_message: error.message.truncate(500),
        completed_at: Time.current
      )
    end
  end

  def ensure_active!(qualification)
    return if active?(qualification)

    raise InvalidState, "La qualification #{qualification.id} n'appartient plus à cette exécution."
  end

  def active?(qualification)
    qualification.running? && qualification.execution_job_id == job_id
  end

  def attach_partial(qualification, result)
    attach_artifacts(qualification, result, partial: true)
  end

  def attach_artifacts(qualification, result, partial:)
    RESULT_ARTIFACTS.each do |attachment_name, result_name, filename, content_type, required|
      content = result.public_send(result_name)
      next if content.blank? && (partial || !required)

      attach(qualification.public_send(attachment_name), content, filename, content_type)
    end
  end
end
