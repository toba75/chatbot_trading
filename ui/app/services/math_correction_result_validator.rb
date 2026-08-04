require "digest"
require "json"
require "nokogiri"

class MathCorrectionResultValidator
  class InvalidResult < StandardError; end

  def initialize(result, native_document:)
    @result = result
    @native_document = native_document
  end

  def validate(correction, target_region_ids:)
    counts = correction_counts(correction)
    status = expected_status(counts)
    reject! unless correction["status"] == status
    validate_artifacts(correction, counts)
    records = validate_records(counts, target_region_ids)
    validate_derived_outputs(counts, records)
    counts.merge("status" => status, "engine" => correction["engine"])
  rescue JSON::ParserError, Nokogiri::XML::SyntaxError
    reject!
  end

  private

  def correction_counts(correction)
    reject! unless correction.is_a?(Hash)
    counts = %w[regions targets accepted accepted_regions rejected failed].to_h do |name|
      value = correction[name]
      reject! unless value.is_a?(Integer) && value >= 0
      [ name, value ]
    end
    reject! unless counts.fetch("targets") == counts.values_at("accepted", "rejected", "failed").sum
    reject! if counts.fetch("accepted_regions") > counts.fetch("regions")
    counts
  end

  def expected_status(counts)
    return "failed" if counts.fetch("failed").positive?
    return "corrected" if counts.fetch("accepted").positive?
    return "rejected" if counts.fetch("targets").positive?

    "not_required"
  end

  def validate_artifacts(correction, counts)
    contents = {
      "corrections" => @result.corrections,
      "correction_evidence" => @result.correction_evidence,
      "derived_docling_document" => @result.derived_docling_document,
      "derived_html" => @result.derived_html,
      "derived_markdown" => @result.derived_markdown
    }
    names = %w[corrections correction_evidence]
    names += MathQualificationClient::DERIVED_ARTIFACT_NAMES if counts.fetch("accepted").positive?
    artifacts = correction["artifacts"]
    reject! unless artifacts.is_a?(Hash) && artifacts.keys.sort == names.sort
    names.each do |name|
      metadata = artifacts[name]
      content = contents.fetch(name)
      reject! unless metadata.is_a?(Hash) &&
        metadata["bytes"] == content.bytesize &&
        metadata["sha256"] == Digest::SHA256.hexdigest(content)
    end
    reject! unless (MathQualificationClient::DERIVED_ARTIFACT_NAMES - names).all? do |name|
      contents.fetch(name).empty?
    end
  end

  def validate_records(counts, target_region_ids)
    payload = JSON.parse(@result.corrections)
    reject! unless payload.is_a?(Hash)
    records = payload["records"]
    reject! unless records.is_a?(Array) && records.all? { |record| record.is_a?(Hash) }
    reject! unless records.size == counts.fetch("targets")
    record_region_ids = records.flat_map { |record| record["region_ids"] }
    reject! unless record_region_ids.uniq.size == record_region_ids.size
    reject! unless record_region_ids.sort == target_region_ids.sort
    reject! unless counts.fetch("regions") == target_region_ids.size
    reject! unless records.all? { |record| valid_record?(record) }
    tallies = records.map { |record| record["status"] }.tally
    %w[accepted rejected failed].each do |status|
      reject! unless tallies.fetch(status, 0) == counts.fetch(status)
    end
    accepted_regions = records.sum do |record|
      record["status"] == "accepted" ? record["region_ids"].size : 0
    end
    reject! unless accepted_regions == counts.fetch("accepted_regions")
    summary = payload["summary"]
    valid_summary = summary.is_a?(Hash) &&
      %w[status regions targets accepted accepted_regions rejected failed].all? do |name|
        summary[name] == (name == "status" ? expected_status(counts) : counts.fetch(name))
      end
    reject! unless valid_summary
    records
  end

  def valid_record?(record)
    return false unless record["target_id"].is_a?(String)
    return false unless record["region_ids"].is_a?(Array) && record["region_ids"].any?
    return false unless record["region_ids"].all? { |identifier| identifier.is_a?(String) }
    return false unless record["region_id"] == record["region_ids"].first
    return record["reason"].is_a?(String) if %w[rejected failed].include?(record["status"])
    return false unless record["status"] == "accepted"

    valid_accepted_record?(record)
  end

  def valid_accepted_record?(record)
    return false unless record["page"].is_a?(Integer) && record["page"].positive?
    return false unless record["after"].is_a?(String)
    return false unless record["mathml"].is_a?(String) && record["mathml"].start_with?("<math ")
    return false unless valid_source_proofs?(record) && valid_proposals?(record)
    return false if record["kind"] == "formula_insertion"
    return false unless valid_formula_replacement_output?(record)

    record["docling_ref"].is_a?(String) &&
      record["charspan"].is_a?(Array) && record["charspan"].size == 2 &&
      record["charspan"].all? { |value| value.is_a?(Integer) } &&
      record["before"].is_a?(String)
  end

  def valid_source_proofs?(record)
    proofs = record["source_proofs"]
    proofs.is_a?(Array) && proofs.size == record["region_ids"].size &&
      proofs.map { |proof| proof["region_id"] } == record["region_ids"] &&
      proofs.all? do |proof|
        proof["tokens"].is_a?(Array) && proof["signature"].is_a?(Array)
      end
  end

  def valid_proposals?(record)
    proposals = record["proposals"]
    proposals.is_a?(Array) && proposals.size == record["region_ids"].size &&
      proposals.zip(record["source_proofs"]).all? do |proposal, proof|
        proposal["selected_engine"].is_a?(String) &&
          proposal["proposal_tokens"] == proof["tokens"] &&
          proposal["proposal_signature"] == proof["signature"] &&
          valid_vision_evidence?(
            proposal,
            proof: proof,
            required: record["kind"] == "formula_replacement"
          )
      end
  end

  def valid_vision_evidence?(proposal, proof:, required:)
    return false if required && !proposal.key?("vision_proposal")
    return true unless proposal.key?("vision_proposal")

    proposal["selected_engine"] == "vision_proven_by_source" &&
      proposal["vision_proposal"].is_a?(String) && proposal["vision_proposal"].present? &&
      proposal["vision_proposal_tokens"] == proof["tokens"] &&
      proposal["vision_proposal_signature"] == proof["signature"] &&
      proposal["crop_sha256"].is_a?(String) &&
      proposal["crop_sha256"].match?(/\A[0-9a-f]{64}\z/) &&
      proposal["vision_confirmation"] == "exact"
  end

  def valid_formula_replacement_output?(record)
    return true unless record["kind"] == "formula_replacement"

    replacements = record["source_proofs"].zip(record["proposals"]).map do |proof, proposal|
      span = proof["candidate_charspan"]
      return false unless span.is_a?(Array) && span.size == 2
      return false unless span.all? { |value| value.is_a?(Integer) }
      return false unless proof["candidate_text"].is_a?(String)

      [ span, proof["candidate_text"], normalized_latex(proposal["vision_proposal"]) ]
    end.sort_by { |span, _before, _after| span.first }
    return false if replacements.each_cons(2).any? { |left, right| left.first.last > right.first.first }

    reconstructed = record["before"].dup
    replacements.reverse_each do |span, before, after|
      start, finish = span
      return false unless 0 <= start && start < finish && finish <= reconstructed.length
      return false unless reconstructed[start...finish] == before

      reconstructed[start...finish] = after
    end
    reconstructed == record["after"]
  end

  def normalized_latex(latex)
    latex.gsub(/\\arg\b/, "\\operatorname{arg}")
  end

  def validate_derived_outputs(counts, records)
    return if counts.fetch("accepted").zero?

    native = JSON.parse(@native_document)
    derived = JSON.parse(@result.derived_docling_document)
    reject! unless native.is_a?(Hash) && derived.is_a?(Hash)
    accepted = records.select { |record| record["status"] == "accepted" }
    apply_records!(native, accepted)
    reject! unless same_docling_value?(derived, native)
    validate_html_pages!(native, accepted)

    markdown = @result.derived_markdown
      .gsub("&lt;", "<")
      .gsub("&gt;", ">")
      .gsub("&amp;", "&")
      .gsub("\\_", "_")
    reject! unless accepted.all? { |record| markdown.include?(record["after"].gsub("\\_", "_")) }
  end

  def validate_html_pages!(native, accepted)
    page_numbers = native["pages"]&.keys&.map { |value| Integer(value, exception: false) }
    reject! unless page_numbers&.all? && page_numbers.uniq.size == page_numbers.size

    html = Nokogiri::HTML5.parse(@result.derived_html)
    visible_math = html.css("math").flat_map do |math|
      math.xpath(
        ".//text()[not(ancestor::*[local-name()='annotation'])]"
      ).map(&:text)
    end.join
    reject! if visible_math.match?(/\\[A-Za-z]+/)

    pages = html.css("div.page[id]")
    html_page_numbers = pages.filter_map do |page|
      match = /\Apage-(\d+)\z/.match(page["id"])
      Integer(match[1]) if match
    end
    reject! unless html_page_numbers.sort == page_numbers.sort && pages.size == page_numbers.size

    correction_nodes = html.css("math[data-correction-id]")
    reject! unless correction_nodes.map { |math| math["data-correction-id"] }.sort ==
      accepted.map { |record| record.fetch("target_id") }.sort

    accepted.each do |record|
      matches = correction_nodes.select do |math|
        math["data-correction-id"] == record.fetch("target_id")
      end
      reject! unless matches.one?

      page = matches.first.ancestors("div.page").first
      reject! unless page&.[]("id") == "page-#{record.fetch("page")}"

      expected = Nokogiri::HTML5.fragment(record.fetch("mathml"))
      reject! unless expected.element_children.one?
      reject! unless matches.first.to_html == expected.element_children.first.to_html
    end
  end

  def apply_records!(document, records)
    texts = document["texts"]
    reject! unless document["schema_name"] == "DoclingDocument" && texts.is_a?(Array)
    records.group_by { |record| record["docling_ref"] }.each do |reference, group|
      match = /\A#\/texts\/(\d+)\z/.match(reference)
      reject! unless match
      node = texts[Integer(match[1])]
      reject! unless node.is_a?(Hash) && node["text"].is_a?(String)
      ordered = group.sort_by { |record| record["charspan"][0] }
      reject! if ordered.each_cons(2).any? { |left, right| right["charspan"][0] < left["charspan"][1] }
      ordered.reverse_each do |record|
        start_at, end_at = record["charspan"]
        reject! unless node["text"][start_at...end_at] == record["before"]
        node["text"] = node["text"][...start_at] + record["after"] + node["text"][end_at...]
      end
    end
  end

  def same_docling_value?(left, right)
    if left.is_a?(Hash) && right.is_a?(Hash)
      left = normalized_hash(left)
      right = normalized_hash(right)
      return left.keys.sort == right.keys.sort && left.all? do |key, child|
        same_docling_value?(child, right.fetch(key))
      end
    end
    return false unless left.class == right.class
    return left.size == right.size && left.zip(right).all? { |pair| same_docling_value?(*pair) } if left.is_a?(Array)

    left == right
  end

  def normalized_hash(value)
    value.to_h { |key, child| [ key == "$ref" ? "cref" : key, child ] }
  end

  def reject!
    raise InvalidResult
  end
end
