require "json"
require "stringio"

class QualifyMathJob < ApplicationJob
  class InvalidState < StandardError; end
  class InterruptedExecution < StandardError; end

  queue_as :math_qualifications
  self.enqueue_after_transaction_commit = false

  def perform(qualification)
    begin_qualification!(qualification)
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
    qualification.with_lock do
      if qualification.queued?
        qualification.update!(
          status: "running",
          phase: "source_analysis",
          completed_units: 0,
          total_units: 1,
          started_at: Time.current,
          execution_job_id: job_id
        )
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
    return unless interrupted

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
      "coverage" => %w[pages_total pages_traced pages_unsupported pages_ambiguous].to_h do |name|
        value = coverage[name]
        invalid_report!(result) unless value.is_a?(Integer) && value >= 0
        [ name, value ]
      end,
      "region_details" => regions_detail.map { |region| region_summary(region, result) },
      "page_exclusions" => pages.filter_map { |page| page_exclusion(page, result) }
    }
    invalid_report!(result) unless summary.dig("coverage", "pages_total") == pages.size
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

  def region_summary(region, result)
    values = region.values_at("region_id", "page", "bbox", "verdict", "semantic_reasons")
    invalid_report!(result) unless values[0].is_a?(String) && values[1].is_a?(Integer) &&
      values[2].is_a?(Array) && values[3].is_a?(String) && values[4].is_a?(Array)
    {
      "id" => values[0],
      "page" => values[1],
      "bbox" => values[2],
      "verdict" => values[3],
      "reasons" => values[4]
    }
  end

  def page_exclusion(page, result)
    return if page["status"] == "traced"

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

  def invalid_report!(result)
    raise MathQualificationClient::QualificationError.new(
      "invalid_report",
      "Le rapport de qualification mathématique est invalide.",
      result: result
    )
  end

  def attach_result(qualification, result)
    attach(qualification.analyzer_response, result.raw_response, "response.ndjson", "application/x-ndjson")
    attach(qualification.source_evidence, result.evidence, "evidence.ndjson.gz", "application/gzip")
    attach(qualification.report, result.report_bytes, "report.json", "application/json")
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
    attach(qualification.analyzer_response, result.raw_response, "response.ndjson", "application/x-ndjson") if result.raw_response.present?
    attach(qualification.source_evidence, result.evidence, "evidence.ndjson.gz", "application/gzip") if result.evidence.present?
    attach(qualification.report, result.report_bytes, "report.json", "application/json") if result.report_bytes.present?
  end
end
