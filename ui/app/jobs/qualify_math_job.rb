require "digest"
require "json"
require "stringio"

class QualifyMathJob < ApplicationJob
  RENDERED_PAGE_AMBIGUITY_CODES = %w[
    rendered_font_resource_ambiguous rendered_font_mismatch rendered_gid_mismatch
  ].freeze
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
  self.enqueue_after_transaction_commit = true

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
      if qualification_waiting_for_job?(qualification) && !qualification.current_contract?
        qualification.update!(
          status: "failed",
          error_code: "obsolete_contract",
          error_message: "Cette qualification historique doit être recréée avec le contrat courant.",
          completed_at: Time.current
        )
      elsif qualification_ready_for_job?(qualification)
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

  def qualification_waiting_for_job?(qualification)
    qualification.staging? || qualification.queued?
  end

  def qualification_ready_for_job?(qualification)
    qualification_waiting_for_job?(qualification) &&
      (qualification.execution_job_id.blank? || qualification.execution_job_id == job_id)
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
    end
    attach_result(qualification, result)
    qualification.with_lock do
      ensure_active!(qualification)
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
    native_document = qualification.conversion_attempt.docling_document.download
    correction = correction_summary(
      report["correction"],
      result,
      available_region_ids: regions_detail.map { |region| region["region_id"] },
      native_document: native_document
    )
    correction_records = JSON.parse(result.corrections).fetch("records")
      .select { |record| record["status"] == "accepted" }
    html_document = correction["accepted"].positive? ?
      result.derived_docling_document : native_document
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
      "page_exclusions" => pages.filter_map { |page| page_exclusion(page, result) },
      "html_integrity" => html_integrity_summary(
        report["html_integrity"], regions_detail, result,
        document: html_document, corrections: correction_records
      ),
      "correction" => correction
    }
    expected_html_artifact = summary.dig("correction", "accepted").positive? ?
      "derived_html" : "native_page_html"
    invalid_report!(result) unless
      summary.dig("html_integrity", "artifact") == expected_html_artifact
    invalid_report!(result) unless summary.dig("coverage", "pages_total") == pages.size
    invalid_report!(result) unless
      summary.dig("html_integrity", "pages_total") == summary.dig("coverage", "pages_total")
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

  def html_integrity_summary(integrity, regions_detail, result, document:, corrections:)
    region_links = integrity.is_a?(Hash) ? integrity["region_links"] : nil
    pages = integrity.is_a?(Hash) ? integrity["pages"] : nil
    valid = integrity.is_a?(Hash) &&
      %w[native_page_html derived_html].include?(integrity["artifact"]) &&
      %w[passed failed].include?(integrity["status"]) &&
      integrity["pages_total"].is_a?(Integer) && integrity["pages_total"].positive? &&
      integrity["pages_checked"].is_a?(Integer) &&
      integrity["pages_checked"] == integrity["pages_total"] &&
      pages.is_a?(Array) && pages.size == integrity["pages_total"] &&
      pages.all? { |page| valid_html_integrity_page?(page) } &&
      pages.map { |page| page["page"] }.sort == (1..integrity["pages_total"]).to_a &&
      integrity["issues"].is_a?(Array) && integrity["issues"].all? do |issue|
        issue.is_a?(Hash) && issue["page"].is_a?(Integer) &&
          issue["code"].is_a?(String) && issue["code"].present? &&
          issue["message"].is_a?(String) && issue["message"].present?
      end && region_links.is_a?(Array) && region_links.all? do |link|
        link.is_a?(Hash) && link["region_id"].is_a?(String) &&
          link["page"].is_a?(Integer) && link["docling_ref"].is_a?(String) &&
          link["candidate_charspan"].is_a?(Array) &&
          link["candidate_charspan"].size == 2 &&
          link["candidate_charspan"].all?(Integer) &&
          link["dom_charspan"].is_a?(Array) && link["dom_charspan"].size == 2 &&
          link["dom_charspan"].all?(Integer) &&
          link["dom_selector"].is_a?(String) && link["matches"].is_a?(Integer) &&
          valid_region_link_status?(link)
      end
    if valid
      parsed_document = JSON.parse(document)
      document_texts = parsed_document["texts"]&.index_by { |item| item["self_ref"] }
      corrections_by_region = corrections.each_with_object({}) do |record, index|
        record["region_ids"].each { |region_id| index[region_id] = record }
      end
      regions_by_id = regions_detail.index_by { |region| region["region_id"] }
      expected_region_ids = regions_detail.filter_map do |region|
        region["region_id"] if region["candidate_link_status"] == "linked" &&
          region["verdict"] != "non_verifiable"
      end
      actual_region_ids = region_links.map { |link| link["region_id"] }
      issue_pages = integrity["issues"].map { |issue| issue["page"] }.uniq
      valid = expected_region_ids.uniq.size == expected_region_ids.size &&
        actual_region_ids.uniq.size == actual_region_ids.size &&
        actual_region_ids.sort == expected_region_ids.sort &&
        integrity["issues"].all? do |issue|
          issue["page"].between?(1, integrity["pages_total"])
        end &&
        region_links.all? do |link|
          region = regions_by_id[link["region_id"]]
          valid_region_link_identity?(
            link, region, document_texts, corrections, corrections_by_region
          )
        end &&
        pages.all? do |page|
          (page["status"] == "failed") == issue_pages.include?(page["page"])
        end
    end
    invalid_report!(result) unless valid
    invalid_report!(result) unless (integrity["status"] == "passed") == integrity["issues"].empty?
    integrity.slice(
      "artifact", "status", "pages_total", "pages_checked", "issues", "pages", "region_links"
    )
  end

  def valid_region_link_status?(link)
    case link["status"]
    when "matched", "wrong_page" then link["matches"] == 1
    when "missing" then link["matches"].zero?
    when "duplicated" then link["matches"] > 1
    else false
    end
  end

  def valid_region_link_identity?(link, region, document_texts, corrections, corrections_by_region)
    return false unless region.is_a?(Hash) && document_texts.is_a?(Hash) &&
      link["page"] == region["page"] &&
      link["candidate_charspan"] == region["candidate_charspan"]

    correction = corrections_by_region[region["region_id"]]
    reference = correction&.fetch("derived_docling_ref", nil) || region["docling_ref"]
    item = document_texts[reference]
    return false unless item.is_a?(Hash) && item["text"].is_a?(String) &&
      link["docling_ref"] == reference

    expected_span = if correction
      correction["derived_charspan"]
    else
      mapped_candidate_span(region, corrections)
    end
    expected_span = [ 0, item["text"].length ] if item["label"] == "formula" && !correction
    return false unless link["dom_charspan"] == expected_span

    start, finish = expected_span
    locus = "#{start}:#{finish}"
    expected_text = correction ? correction["after"] :
      (item["label"] == "formula" ? item["text"] : region["candidate_text"])
    start >= 0 && finish > start && finish <= item["text"].length &&
      item["text"][start...finish] == expected_text &&
      link["dom_selector"].include?(
        "[@data-docling-ref='#{link['docling_ref']}']" \
        "[@data-docling-charspan='#{locus}']"
      )
  end

  def mapped_candidate_span(region, corrections)
    span = region["candidate_charspan"]
    return unless span.is_a?(Array) && span.size == 2

    start, finish = span
    shift = 0
    corrections.select { |record| record["docling_ref"] == region["docling_ref"] }
      .sort_by { |record| record["charspan"][0] }
      .each do |record|
        correction_start, correction_finish = record["charspan"]
        if correction_finish <= start
          shift += record["after"].length - (correction_finish - correction_start)
        elsif correction_start < finish
          return
        end
      end
    [ start + shift, finish + shift ]
  end

  def valid_html_integrity_page?(page)
    valid = page.is_a?(Hash) && page["page"].is_a?(Integer) && page["page"].positive? &&
      %w[passed failed].include?(page["status"]) &&
      %w[expected rendered].all? do |name|
        counts = page[name]
        counts.is_a?(Hash) && (counts.keys - %w[math images]).empty? &&
          counts.values.all? { |count| count.is_a?(Integer) && count >= 0 }
      end
    valid && (page["status"] != "passed" || normalized_counts(page["expected"]) ==
      normalized_counts(page["rendered"]))
  end

  def normalized_counts(counts)
    %w[math images].to_h { |name| [ name, counts.fetch(name, 0) ] }
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
      invalid_report!(result) if page.fetch("opaque_regions", []).any? ||
        page.fetch("font_exclusions", []).any?
      return
    end

    if page["status"] == "traced_with_exclusions"
      regions = page["opaque_regions"]
      invalid_report!(result) unless regions.is_a?(Array) && regions.any? &&
        regions.all? { |region| valid_opaque_exclusion?(region) }
      invalid_report!(result) if page.fetch("font_exclusions", []).any?
      reasons = regions.map { |region| region["reason"] }.uniq
      return {
        "page" => page["page"], "status" => page["status"],
        "reasons" => reasons,
        "regions" => regions.map do |region|
          region.slice(
            "kind", "resource", "bbox", "operation_indices", "glyph_sequence_indices"
          )
        end
      }
    end

    if page["status"] == "partially_traced"
      font_regions = page["font_exclusions"]
      opaque_regions = page.fetch("opaque_regions", [])
      invalid_report!(result) unless font_regions.is_a?(Array) && font_regions.any?
      invalid_report!(result) unless font_regions.all? { |region| valid_font_exclusion?(region) }
      invalid_report!(result) unless opaque_regions.is_a?(Array) &&
        opaque_regions.all? { |region| valid_opaque_exclusion?(region) }
      font_reasons = font_regions.flat_map { |region| region.fetch("reasons") }.uniq
      invalid_report!(result) unless canonical_reasons(page["reasons"]) ==
        canonical_reasons(font_reasons)
      reasons = (font_reasons + opaque_regions.map { |region| region.fetch("reason") }).uniq
      return {
        "page" => page["page"], "status" => page["status"],
        "reasons" => reasons,
        "regions" => font_regions.map do |region|
          index_evidence = region.slice(
            "operation_indices", "glyph_sequence_indices",
            "operation_index_ranges", "glyph_sequence_index_ranges"
          )
          {
            "kind" => "font",
            "resource" => region.fetch("resources").join(", "),
            "bbox" => region.fetch("bbox")
          }.merge(index_evidence)
        end + opaque_regions.map do |region|
          region.slice(
            "kind", "resource", "bbox", "operation_indices", "glyph_sequence_indices"
          )
        end
      }
    end

    reasons = page["reasons"]
    font_reasons = reasons&.select { |reason| reason.is_a?(Hash) && reason["font_resource"] }
    font_regions = page.fetch("font_exclusions", [])
    opaque_regions = page.fetch("opaque_regions", [])
    invalid_report!(result) unless page["page"].is_a?(Integer) &&
      valid_bbox?(page["box"]) && valid_reasons?(reasons) &&
      font_regions.is_a?(Array) && opaque_regions.is_a?(Array) &&
      opaque_regions.all? { |region| valid_opaque_exclusion?(region) }
    invalid_report!(result) if reasons.any? do |reason|
      font_limitation_code?(reason["code"], page_status: page["status"]) &&
        !reason["font_resource"].is_a?(String)
    end
    if font_reasons.any?
      invalid_report!(result) unless font_regions.any? &&
        font_regions.all? { |region| valid_font_exclusion?(region) }
      represented_reasons = font_regions.flat_map { |region| region.fetch("reasons") }.uniq
      invalid_report!(result) unless canonical_reasons(font_reasons) ==
        canonical_reasons(represented_reasons)
    else
      invalid_report!(result) if font_regions.any?
    end
    regions = font_regions.map do |region|
      index_evidence = region.slice(
        "operation_indices", "glyph_sequence_indices",
        "operation_index_ranges", "glyph_sequence_index_ranges"
      )
      {
        "kind" => "font", "resource" => region.fetch("resources").join(", "),
        "bbox" => region.fetch("bbox")
      }.merge(index_evidence)
    end + opaque_regions.map do |region|
      region.slice(
        "kind", "resource", "bbox", "operation_indices", "glyph_sequence_indices"
      )
    end
    if regions.empty?
      regions = reasons.map do |reason|
        { "kind" => "page", "resource" => reason.fetch("code"), "bbox" => page.fetch("box") }
      end
    end
    {
      "page" => page["page"], "status" => page["status"], "reasons" => reasons,
      "regions" => regions
    }
  end

  def font_limitation_code?(code, page_status:)
    return false if page_status == "ambiguous" && RENDERED_PAGE_AMBIGUITY_CODES.include?(code)

    code.is_a?(String) && code.match?(
      /(?:font|glyph|encoding|unicode|cmap|cid|gid|type0|type1|truetype|agl)/
    )
  end

  def valid_font_exclusion?(region)
    resources = region["resources"]
    reasons = region["reasons"]
    reason_resources = reasons.filter_map do |reason|
      reason["font_resource"] if reason.is_a?(Hash)
    end if reasons.is_a?(Array)
    %w[line page].include?(region["scope"]) &&
      region["kind"] == "font" &&
      resources.is_a?(Array) && resources.any? &&
      resources.all? { |resource| resource.is_a?(String) && resource.present? } &&
      resources.uniq == resources &&
      reason_resources&.sort == resources.sort &&
      region["trace_font"].is_a?(String) && region["trace_font"].present? &&
      valid_bbox?(region["bbox"]) && valid_reasons?(reasons) &&
      valid_index_evidence?(region, "operation") &&
      valid_index_evidence?(region, "glyph_sequence") &&
      nonempty_index_evidence?(region, "operation") &&
      nonempty_index_evidence?(region, "glyph_sequence")
  end

  def valid_opaque_exclusion?(region)
    %w[form_xobject image_xobject].include?(region["kind"]) &&
      region["resource"].is_a?(String) && region["resource"].present? &&
      valid_bbox?(region["bbox"]) && valid_reasons?([ region["reason"] ]) &&
      valid_indices?(region["operation_indices"]) &&
      valid_indices?(region["glyph_sequence_indices"])
  end

  def valid_bbox?(bbox)
    bbox.is_a?(Array) && bbox.size == 4 &&
      bbox.all? { |coordinate| coordinate.is_a?(Numeric) && coordinate.finite? } &&
      bbox[0] < bbox[2] && bbox[1] < bbox[3]
  end

  def valid_indices?(indices)
    indices.is_a?(Array) && indices.all? { |index| index.is_a?(Integer) && index >= 0 } &&
      indices.uniq == indices && indices == indices.sort
  end

  def valid_index_evidence?(region, prefix)
    indices_key = "#{prefix}_indices"
    ranges_key = "#{prefix}_index_ranges"
    has_indices = region.key?(indices_key)
    has_ranges = region.key?(ranges_key)
    return false if has_indices == has_ranges

    has_indices ? valid_indices?(region[indices_key]) : valid_index_ranges?(region[ranges_key])
  end

  def nonempty_index_evidence?(region, prefix)
    values = region["#{prefix}_indices"] || region["#{prefix}_index_ranges"]
    values.is_a?(Array) && values.any?
  end

  def valid_index_ranges?(ranges)
    return false unless ranges.is_a?(Array) && ranges.all? do |range|
      range.is_a?(Array) && range.size == 2 &&
        range.all? { |value| value.is_a?(Integer) && value >= 0 } &&
        range[0] <= range[1]
    end

    ranges.each_cons(2).all? { |left, right| left[1] + 1 < right[0] }
  end

  def valid_reasons?(reasons)
    reasons.is_a?(Array) && reasons.any? && reasons.all? do |reason|
      reason.is_a?(Hash) && reason["code"].is_a?(String) && reason["code"].present? &&
        reason["message"].is_a?(String) && reason["message"].present?
    end
  end

  def canonical_reasons(reasons)
    return unless valid_reasons?(reasons)

    reasons.map { |reason| reason.slice("font_resource", "code", "message") }.sort_by do |reason|
      [ reason["font_resource"].to_s, reason.fetch("code"), reason.fetch("message") ]
    end
  end

  def aggregate_verdict(summary)
    return "contradicted" if summary.fetch("contradicted").positive?
    return "non_verifiable" if summary.fetch("regions").zero?
    return "non_verifiable" if summary.fetch("non_verifiable") == summary.fetch("regions")
    return "partial" if summary.fetch("non_verifiable").positive?

    "conformant_within_scope"
  end

  def correction_summary(correction, result, available_region_ids:, native_document:)
    MathCorrectionResultValidator.new(
      result,
      native_document: native_document
    ).validate(
      correction, available_region_ids: available_region_ids
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
    output_error_message = nil
    qualification.with_lock { return unless active?(qualification) }
    if error.result
      begin
        attach_partial(qualification, error.result)
      rescue StandardError => output_error
        output_error_message = "Les preuves partielles n'ont pas pu être stockées : #{output_error.message}"
      end
    end

    qualification.with_lock do
      return unless active?(qualification)

      qualification.update!(
        status: "failed",
        error_code: error.code,
        error_message: [ error.message, output_error_message ].compact.join(" ").truncate(500),
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
