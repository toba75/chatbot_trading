require "json"
require "net/http"
require "openssl"
require "uri"

class GoogleBooksMetadataEnricher
  ENDPOINT = "https://www.googleapis.com/books/v1/volumes"
  MIN_TITLE_SIMILARITY = 0.72
  MAX_AUTHORS = 3
  RESOLUTION_FIELDS = %w[volume_id resolution confirmed_at rejected_at].freeze
  REVIEWABLE_STATUSES = %w[ambiguous review_required].freeze

  class ConfigurationError < StandardError; end
  class ProviderError < StandardError; end
  class CandidateNotFound < StandardError; end

  def self.call(document, transport: nil, api_key: nil)
    new(document, transport: transport, api_key: api_key).call
  end

  def self.confirm(document, volume_id:)
    new(document, transport: nil, api_key: nil).confirm(volume_id)
  end

  def self.reject(document)
    new(document, transport: nil, api_key: nil).reject
  end

  def initialize(document, transport:, api_key:)
    @document = document
    @transport = transport
    @api_key = api_key
  end

  def call
    queries = []
    expected_title = title_for_similarity
    observed_at = Time.current.utc.iso8601
    attempts = []
    normalized_candidates = []
    search_queries.each do |current_query|
      queries << current_query
      payload = fetch(current_query)
      raise ProviderError, "La réponse Google Books n’est pas un objet JSON." unless payload.is_a?(Hash)
      raise ProviderError, "La réponse Google Books contient une liste items invalide." if payload.key?("items") && !payload["items"].is_a?(Array)

      items = Array(payload["items"])
      attempts << { "query" => current_query, "candidate_count" => items.size }
      normalized_candidates.concat(items.map do |item|
        normalize_candidate(item, observed_at, expected_title, current_query)
      end)
    end
    if identifier_queries_present? && !normalized_candidates.compact.any? { |candidate| coherent_identifier_match?(candidate, expected_title) }
      title_search_queries.each do |current_query|
        queries << current_query
        payload = fetch(current_query)
        raise ProviderError, "La réponse Google Books n’est pas un objet JSON." unless payload.is_a?(Hash)
        raise ProviderError, "La réponse Google Books contient une liste items invalide." if payload.key?("items") && !payload["items"].is_a?(Array)

        items = Array(payload["items"])
        attempts << { "query" => current_query, "candidate_count" => items.size }
        normalized_candidates.concat(items.map do |item|
          normalize_candidate(item, observed_at, expected_title, current_query)
        end)
      end
    end
    query = queries.first
    candidates = merge_candidates(normalized_candidates.compact)
    score_candidates!(candidates)
    status, selected, review_candidate_ids = resolve(candidates)
    metadata = existing_metadata
    enrichment = metadata.fetch("enrichment", {}).merge(
      "provider" => "google_books",
      "status" => status,
      "observed_at" => observed_at,
      "query" => query,
      "queries" => queries,
      "attempts" => attempts,
      "candidate_count" => candidates.size,
      "invalid_candidate_count" => normalized_candidates.count(&:nil?),
      "review_candidate_ids" => review_candidate_ids,
      "candidates" => candidates
    )
    clear_resolution_fields!(enrichment)
    enrichment.delete("error")
    metadata["enrichment"] = enrichment
    if status == "accepted"
      metadata["bibliography"] = bibliography_from(selected)
      metadata["enrichment"].merge!(
        "volume_id" => selected["volume_id"],
        "resolution" => "automatic"
      )
    end
    metadata
  rescue ConfigurationError => error
    failure_metadata("configuration_error", error.message)
  rescue ProviderError, JSON::ParserError, Net::OpenTimeout, Net::ReadTimeout,
         SocketError, IOError, EOFError, Net::HTTPBadResponse,
         SystemCallError, OpenSSL::SSL::SSLError => error
    failure_metadata("provider_unavailable", error.message)
  end

  def confirm(volume_id)
    metadata = existing_metadata
    enrichment = metadata.fetch("enrichment", {})
    raise CandidateNotFound unless REVIEWABLE_STATUSES.include?(enrichment["status"])

    candidate = Array(enrichment["candidates"]).find do |entry|
      entry.is_a?(Hash) && entry["volume_id"].to_s == volume_id.to_s
    end
    raise CandidateNotFound unless candidate
    review_ids = Array(enrichment["review_candidate_ids"]).map(&:to_s)
    raise CandidateNotFound if review_ids.any? && !review_ids.include?(candidate["volume_id"].to_s)
    raise CandidateNotFound if review_ids.empty? && candidate["score"].present? && candidate["score"].to_f < MIN_TITLE_SIMILARITY

    metadata["bibliography"] = bibliography_from(candidate)
    metadata["enrichment"] = clear_resolution_fields!(enrichment).merge(
      "status" => "accepted",
      "resolution" => "manual",
      "volume_id" => candidate["volume_id"],
      "confirmed_at" => Time.current.utc.iso8601
    ).tap { |value| value.delete("error") }
    metadata
  end

  def reject
    metadata = existing_metadata
    enrichment = metadata.fetch("enrichment", {})
    raise CandidateNotFound unless REVIEWABLE_STATUSES.include?(enrichment["status"])

    enrichment = clear_resolution_fields!(enrichment).merge(
      "status" => "no_match",
      "resolution" => "manual_rejection",
      "rejected_at" => Time.current.utc.iso8601
    )
    enrichment.delete("error")
    enrichment.delete("volume_id")
    metadata["enrichment"] = enrichment
    metadata
  end

  private

  def existing_metadata
    @document.metadata.deep_dup.tap { |metadata| metadata["schema_version"] ||= 1 }
  end

  def clear_resolution_fields!(enrichment)
    RESOLUTION_FIELDS.each { |field| enrichment.delete(field) }
    enrichment
  end

  def failure_metadata(code, message)
    metadata = existing_metadata
    enrichment = metadata.fetch("enrichment", {}).merge(
      "provider" => "google_books",
      "status" => code,
      "observed_at" => Time.current.utc.iso8601,
      "query" => search_query,
      "error" => { "code" => code, "message" => message.to_s.truncate(500) }
    )
    metadata["enrichment"] = clear_resolution_fields!(enrichment)
    metadata
  end

  def api_key
    value = @api_key || Rails.application.credentials.dig(:google_books, :api_key)
    value.to_s.strip.presence || raise(ConfigurationError, "La clé Google Books est absente des credentials Rails.")
  end

  def search_query
    search_queries.first
  end

  def search_queries
    identifier_queries = known_isbns.map { |isbn| "isbn:#{isbn}" } + known_issns.map { |issn| "issn:#{issn}" }
    return identifier_queries if identifier_queries.present?

    title_search_queries
  end

  def title_search_queries

    titles = title_variants
    authors = Array(@document.bibliographic_metadata["authors"]).filter_map { |author| author.to_s.presence }.first(MAX_AUTHORS)
    queries = authors.map { |author| "intitle:#{titles.first} inauthor:#{author}" }
    titles.each { |title| queries << "intitle:#{title}" }
    if (publisher = @document.bibliographic_metadata["publisher"].to_s.presence)
      queries << "intitle:#{titles.first} inpublisher:#{publisher}"
    end
    queries.uniq.presence || [ "intitle:#{title_for_similarity}" ]
  end

  def identifier_queries_present?
    known_isbns.present? || known_issns.present?
  end

  def title_for_similarity
    known_title = @document.bibliographic_metadata["title"].presence
    return known_title if known_title

    raw_title = @document.source_pdf.filename.to_s
      .sub(/\.pdf\z/i, "")
      .tr("_", " ")
      .gsub(/\s+/, " ")
      .strip
    raw_title.sub(/\s*[-–]\s*[^-–()]+\s*\((?:19|20)\d{2}\)\s*\z/, "").strip
  end

  def title_variants
    raw_title = @document.source_pdf.filename.to_s
      .sub(/\.pdf\z/i, "")
      .tr("_", " ")
      .gsub(/\s+/, " ")
      .strip
    [ title_for_similarity, raw_title ].compact.uniq.reject(&:blank?)
  end

  def known_isbns
    identifiers = @document.bibliographic_metadata.fetch("identifiers", {})
    Array(identifiers.values).flatten.map { |value| canonical_isbn(value) }.compact.uniq
  end

  def known_issns
    identifiers = @document.bibliographic_metadata.fetch("identifiers", {})
    Array(identifiers["issn"]).filter_map { |value| canonical_issn(value) }.uniq
  end

  def fetch(query)
    uri = URI(ENDPOINT)
    uri.query = URI.encode_www_form(
      q: query,
      maxResults: 40,
      printType: "all",
      key: api_key
    )
    return @transport.call(uri.to_s) if @transport

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = true
    http.open_timeout = 5
    http.read_timeout = 15
    response = http.get(uri.request_uri, { "Accept" => "application/json", "User-Agent" => "chatbot-trading-ui/1" })
    raise ProviderError, "Google Books a répondu HTTP #{response.code}." unless response.is_a?(Net::HTTPSuccess)

    JSON.parse(response.body)
  end

  def normalize_candidate(item, observed_at, expected_title, query)
    return unless item.is_a?(Hash) && item["id"].present?

    info = item["volumeInfo"]
    return unless info.is_a?(Hash) && info["title"].present?

    identifiers = { "isbn10" => [], "isbn13" => [], "issn" => [] }
    Array(info["industryIdentifiers"]).each do |identifier|
      next unless identifier.is_a?(Hash)

      kind = identifier["type"].to_s.upcase
      value = identifier["identifier"].to_s.gsub(/[^0-9Xx]/, "").upcase
      identifiers["isbn10"] << value if kind == "ISBN_10" && value.present?
      identifiers["isbn13"] << value if kind == "ISBN_13" && value.present?
      identifiers["issn"] << value if %w[ISSN ISSN_L].include?(kind) && value.present?
    end
    identifiers.each_value(&:uniq!)
    candidate = {
      "volume_id" => item["id"],
      "title" => info["title"].to_s,
      "authors" => Array(info["authors"]).filter_map { |author| author.to_s.presence },
      "publisher" => info["publisher"].to_s.presence,
      "published_date" => valid_date(info["publishedDate"]),
      "language" => info["language"].to_s.presence,
      "identifiers" => identifiers,
      "proof" => { "provider" => "google_books", "volume_id" => item["id"], "observed_at" => observed_at },
      "score" => title_similarity(expected_title, info["title"]),
      "matched_queries" => [ query ]
    }
    average = info["averageRating"]
    count = info["ratingsCount"]
    candidate["rating"] = { "average" => average.to_f, "count" => count } if average.is_a?(Numeric) && average.between?(0, 5) && count.is_a?(Integer) && count >= 0
    candidate
  end

  def resolve(candidates)
    identifier_matches = candidates.select { |candidate| coherent_identifier_match?(candidate, title_for_similarity) }
    return [ "accepted", identifier_matches.first, identifier_matches.map { |candidate| candidate["volume_id"] } ] if identifier_matches.one?
    return [ "ambiguous", nil, identifier_matches.map { |candidate| candidate["volume_id"] } ] if identifier_matches.size > 1

    plausible = candidates.select { |candidate| candidate["score"] >= MIN_TITLE_SIMILARITY }
    return [ "ambiguous", nil, plausible.map { |candidate| candidate["volume_id"] } ] if plausible.size > 1
    return [ "review_required", nil, plausible.map { |candidate| candidate["volume_id"] } ] if plausible.one?
    [ "no_match", nil, [] ]
  end

  def merge_candidates(candidates)
    candidates.each_with_object({}) do |candidate, grouped|
      current = grouped[candidate["volume_id"]]
      if current
        %w[title subtitle publisher published_date language page_count rating].each do |field|
          current[field] = candidate[field] if current[field].blank? && candidate[field].present?
        end
        %w[authors categories].each do |field|
          current[field] = (Array(current[field]) + Array(candidate[field])).compact.uniq
        end
        current["identifiers"] = current.fetch("identifiers", {}).each_with_object({}) do |(kind, values), identifiers|
          identifiers[kind] = (Array(values) + Array(candidate.dig("identifiers", kind))).compact.uniq
        end
        current["matched_queries"] = (Array(current["matched_queries"]) + Array(candidate["matched_queries"])).uniq
      else
        grouped[candidate["volume_id"]] = candidate
      end
    end.values
  end

  def score_candidates!(candidates)
    candidates.each do |candidate|
      title_score = candidate.fetch("score", 0).to_f
      authors = Array(@document.bibliographic_metadata["authors"]).filter_map { |author| author.to_s.presence }
      candidate_authors = Array(candidate["authors"])
      signals = { "title" => title_score }
      weights = { "title" => 0.60 }
      unless authors.empty?
        signals["author"] = authors.product(candidate_authors).map { |expected, actual| title_similarity(expected, actual) }.max.to_f
        weights["author"] = 0.20
      end
      if (publisher = @document.bibliographic_metadata["publisher"].to_s.presence)
        signals["publisher"] = title_similarity(publisher, candidate["publisher"])
        weights["publisher"] = 0.10
      end
      if (year = publication_year_hint)
        candidate_year = candidate["published_date"].to_s.first(4)
        signals["year"] = year == candidate_year ? 1.0 : 0.0
        weights["year"] = 0.10
      end
      candidate["matching"] = signals.merge(
        "score" => (signals.sum { |name, value| value.to_f * weights.fetch(name) } / weights.values.sum).round(4)
      )
      candidate["score"] = candidate["matching"]["score"]
    end
    candidates.sort_by! { |candidate| -candidate["score"].to_f }
  end

  def publication_year_hint
    value = @document.bibliographic_metadata["publication_year"].presence || @document.bibliographic_metadata["publication_date"].to_s.first(4)
    value.to_s.match?(/\A(?:19|20)\d{2}\z/) ? value.to_s : nil
  end

  def exact_identifier_match?(candidate)
    known_isbns.any? { |isbn| isbn_variants(isbn).intersect?(Array(candidate.dig("identifiers", "isbn10")) + Array(candidate.dig("identifiers", "isbn13"))) } ||
      known_issns.intersect?(Array(candidate.dig("identifiers", "issn")))
  end

  def coherent_identifier_match?(candidate, expected_title)
    return false unless exact_identifier_match?(candidate)

    title_similarity(expected_title, candidate["title"]) >= 0.45 ||
      Array(@document.bibliographic_metadata["authors"]).any? do |author|
        title_similarity(author, Array(candidate["authors"]).join(" ")) >= 0.25
      end
  end

  def canonical_isbn(value)
    normalized = value.to_s.gsub(/[^0-9Xx]/, "").upcase
    return unless normalized.match?(/\A(?:\d{9}[\dX]|\d{13})\z/)

    if normalized.length == 10
      return normalized if normalized.chars.each_with_index.sum { |character, index| (10 - index) * (character == "X" ? 10 : character.to_i) } % 11 == 0
    elsif normalized.length == 13
      return normalized if normalized.chars.each_with_index.sum { |character, index| (index.even? ? 1 : 3) * character.to_i } % 10 == 0
    end
    nil
  end

  def canonical_issn(value)
    normalized = value.to_s.gsub(/[^0-9Xx]/, "").upcase
    return unless normalized.match?(/\A\d{7}[\dX]\z/)

    normalized if normalized.chars.each_with_index.sum { |character, index| (8 - index) * (character == "X" ? 10 : character.to_i) } % 11 == 0
  end

  def isbn_variants(value)
    canonical = canonical_isbn(value)
    return [] unless canonical

    variants = [ canonical ]
    if canonical.length == 10
      body = "978#{canonical[0, 9]}"
      checksum = (10 - body.chars.each_with_index.sum { |character, index| (index.even? ? 1 : 3) * character.to_i } % 10) % 10
      variants << "#{body}#{checksum}"
    elsif canonical.start_with?("978")
      body = canonical[3, 9]
      checksum = (11 - body.chars.each_with_index.sum { |character, index| (10 - index) * character.to_i } % 11) % 11
      variants << "#{body}#{checksum == 10 ? 'X' : checksum}"
    end
    variants
  end

  def bibliography_from(candidate)
    {
      "title" => candidate["title"],
      "authors" => candidate["authors"],
      "publisher" => candidate["publisher"],
      "language" => candidate["language"],
      "publication_date" => candidate["published_date"],
      "publication_year" => candidate["published_date"]&.first(4),
      "identifiers" => candidate["identifiers"],
      "rating" => candidate["rating"]
    }.compact
  end

  def valid_date(value)
    text = value.to_s
    return text if text.match?(/\A\d{4}\z/)

    if text.match?(/\A\d{4}-\d{2}\z/)
      Date.strptime("#{text}-01", "%Y-%m-%d")
      return text
    end
    Date.iso8601(text).iso8601
  rescue ArgumentError
    nil
  end

  def title_similarity(expected, actual)
    left = tokens(expected)
    right = tokens(actual)
    return 0.0 if left.empty? || right.empty?

    (left & right).size.to_f / [ left.size, right.size ].max
  end

  def tokens(value)
    value.to_s.downcase.scan(/[[:alnum:]]+/).uniq
  end
end
