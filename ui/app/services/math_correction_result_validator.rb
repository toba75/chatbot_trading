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
    counts = %w[targets accepted rejected failed].to_h do |name|
      value = correction[name]
      reject! unless value.is_a?(Integer) && value >= 0
      [ name, value ]
    end
    reject! unless counts.fetch("targets") == counts.values_at("accepted", "rejected", "failed").sum
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
    reject! unless records.map { |record| record["region_id"] }.sort == target_region_ids.sort
    reject! unless records.all? { |record| valid_record?(record) }
    tallies = records.map { |record| record["status"] }.tally
    %w[accepted rejected failed].each do |status|
      reject! unless tallies.fetch(status, 0) == counts.fetch(status)
    end
    summary = payload["summary"]
    valid_summary = summary.is_a?(Hash) &&
      %w[status targets accepted rejected failed].all? do |name|
        summary[name] == (name == "status" ? expected_status(counts) : counts.fetch(name))
      end
    reject! unless valid_summary
    records
  end

  def valid_record?(record)
    return false unless record["region_id"].is_a?(String)
    return record["reason"].is_a?(String) if %w[rejected failed].include?(record["status"])
    return false unless record["status"] == "accepted"

    record["page"].is_a?(Integer) && record["page"].positive? &&
      record["docling_ref"].is_a?(String) &&
      record["charspan"].is_a?(Array) && record["charspan"].size == 2 &&
      record["charspan"].all? { |value| value.is_a?(Integer) } &&
      record["before"].is_a?(String) && record["after"].is_a?(String) &&
      record["mathml"].is_a?(String) && record["mathml"].start_with?("<math ") &&
      record["proposal"].is_a?(String) &&
      record["proposal_tokens"] == record["source_tokens"] &&
      record["proposal_signature"] == record["source_signature"] &&
      record["crop_sha256"].is_a?(String) && record["crop_sha256"].match?(/\A[0-9a-f]{64}\z/)
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
    pages = html.css("div.page[id]")
    html_page_numbers = pages.filter_map do |page|
      match = /\Apage-(\d+)\z/.match(page["id"])
      Integer(match[1]) if match
    end
    reject! unless html_page_numbers.sort == page_numbers.sort && pages.size == page_numbers.size

    correction_nodes = html.css("math[data-correction-id]")
    reject! unless correction_nodes.map { |math| math["data-correction-id"] }.sort ==
      accepted.map { |record| record.fetch("region_id") }.sort

    accepted.each do |record|
      matches = correction_nodes.select do |math|
        math["data-correction-id"] == record.fetch("region_id")
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
