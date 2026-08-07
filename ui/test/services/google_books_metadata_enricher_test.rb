require "test_helper"
require "uri"

class GoogleBooksMetadataEnricherTest < ActiveSupport::TestCase
  test "enregistre une correspondance Google Books acceptée sur le document" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: {
      "bibliography" => { "identifiers" => { "isbn13" => [ "978-1-00939-7292" ] } }
    })
    observed_url = nil

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |url|
      observed_url = url
      { "items" => [ volume("causal-1", "Causal Factor Investing") ] }
    })

    assert_includes URI.parse(observed_url).query, "key=secret-test"
    assert_equal "isbn:9781009397292", URI.decode_www_form(URI.parse(observed_url).query).to_h.fetch("q")
    assert_equal "accepted", metadata.dig("enrichment", "status")
    assert_equal "causal-1", metadata.dig("enrichment", "volume_id")
    assert_equal "Causal Factor Investing", metadata.dig("bibliography", "title")
    assert_equal [ "Marcos M. López de Prado" ], metadata.dig("bibliography", "authors")
    assert_equal "2023-10-31", metadata.dig("bibliography", "publication_date")
    assert_equal "2023", metadata.dig("bibliography", "publication_year")
    assert_equal({ "average" => 4.5, "count" => 20 }, metadata.dig("bibliography", "rating"))
  end

  test "conserve les métadonnées précédentes en cas de correspondance ambiguë" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: { "bibliography" => { "publisher" => "Éditeur confirmé" } })

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ volume("causal-1", "Causal Factor Investing"), volume("causal-2", "Causal Factor Investing") ] }
    })

    assert_equal "ambiguous", metadata.dig("enrichment", "status")
    assert_equal "Éditeur confirmé", metadata.dig("bibliography", "publisher")
  end

  test "distingue une correspondance unique à confirmer d'une ambiguïté" do
    document = document_with_filename("causal-factor-investing.pdf")

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ volume("causal-1", "Causal Factor Investing") ] }
    })

    assert_equal "review_required", metadata.dig("enrichment", "status")
    assert_equal 1, metadata.dig("enrichment", "candidate_count")

    document.update!(metadata: metadata)
    confirmed = GoogleBooksMetadataEnricher.confirm(document, volume_id: "causal-1")

    assert_equal "accepted", confirmed.dig("enrichment", "status")
  end

  test "promouvoit uniquement le candidat confirmé par l'utilisateur" do
    document = document_with_filename("causal-factor-investing.pdf")
    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ volume("causal-1", "Causal Factor Investing"), volume("causal-2", "Causal Factor Investing") ] }
    })
    document.update!(metadata: metadata)

    confirmed = GoogleBooksMetadataEnricher.confirm(document, volume_id: "causal-2")

    assert_equal "accepted", confirmed.dig("enrichment", "status")
    assert_equal "manual", confirmed.dig("enrichment", "resolution")
    assert_equal "causal-2", confirmed.dig("enrichment", "volume_id")
    assert_equal "Causal Factor Investing", confirmed.dig("bibliography", "title")
  end

  test "refuse de confirmer un volume absent des candidats" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: {
      "enrichment" => { "status" => "ambiguous", "candidates" => [ { "volume_id" => "known" } ] }
    })

    assert_raises(GoogleBooksMetadataEnricher::CandidateNotFound) do
      GoogleBooksMetadataEnricher.confirm(document, volume_id: "unknown")
    end
  end

  test "rend observable une coupure réseau" do
    document = document_with_filename("causal-factor-investing.pdf")

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      raise Errno::ECONNRESET
    })

    assert_equal "provider_unavailable", metadata.dig("enrichment", "status")
    assert_equal "provider_unavailable", metadata.dig("enrichment", "error", "code")
  end

  test "dÃ©duplique les volumes Google Books par identifiant" do
    document = document_with_filename("causal-factor-investing.pdf")

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => (1..6).map { |index| volume("causal-#{index}", "Causal Factor Investing") } + [ volume("causal-1", "Causal Factor Investing") ] }
    })

    assert_equal 6, metadata.dig("enrichment", "candidate_count")
    assert_equal 6, metadata.dig("enrichment", "candidates").size
    assert_equal 6, metadata.dig("enrichment", "review_candidate_ids").size
  end

  test "ne permet pas de rejeter une mÃ©tadonnÃ©e dÃ©jÃ  confirmÃ©e" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: { "enrichment" => { "status" => "accepted", "volume_id" => "known" } })

    assert_raises(GoogleBooksMetadataEnricher::CandidateNotFound) do
      GoogleBooksMetadataEnricher.reject(document)
    end
  end

  test "conserve le nombre de rÃ©sultats Google Books incomplets" do
    document = document_with_filename("causal-factor-investing.pdf")

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ { "id" => "invalid", "volumeInfo" => nil } ] }
    })

    assert_equal 1, metadata.dig("enrichment", "invalid_candidate_count")
    assert_equal "no_match", metadata.dig("enrichment", "status")
  end

  test "efface une ancienne dÃ©cision quand une nouvelle recherche devient ambiguÃ«" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: {
      "bibliography" => { "title" => "Causal Factor Investing" },
      "enrichment" => {
        "status" => "accepted", "volume_id" => "old-volume", "resolution" => "manual",
        "confirmed_at" => "2026-08-07T15:00:00Z",
        "error" => { "code" => "provider_unavailable", "message" => "ancienne erreur" }
      }
    })

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ volume("causal-1", "Causal Factor Investing"), volume("causal-2", "Causal Factor Investing") ] }
    })

    assert_equal "ambiguous", metadata.dig("enrichment", "status")
    assert_nil metadata.dig("enrichment", "volume_id")
    assert_nil metadata.dig("enrichment", "resolution")
    assert_nil metadata.dig("enrichment", "confirmed_at")
    assert_nil metadata.dig("enrichment", "error")
    assert_equal "Causal Factor Investing", metadata.dig("bibliography", "title")
  end

  test "refuse de promouvoir un candidat masquÃ© par la sÃ©lection" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: {
      "enrichment" => {
        "status" => "review_required",
        "review_candidate_ids" => [ "visible" ],
        "candidates" => [
          { "volume_id" => "visible", "title" => "Titre visible" },
          { "volume_id" => "hidden", "title" => "Titre masqué" }
        ]
      }
    })

    assert_raises(GoogleBooksMetadataEnricher::CandidateNotFound) do
      GoogleBooksMetadataEnricher.confirm(document, volume_id: "hidden")
    end
  end

  test "interroge tous les auteurs et signaux bibliographiques disponibles" do
    document = document_with_filename("source.pdf")
    document.update!(metadata: {
      "bibliography" => {
        "title" => "A Century of Profitable Industry Trends",
        "authors" => [ "Carlo Zarattini", "Gary Antonacci" ],
        "publisher" => "Wiley",
        "publication_year" => "2018"
      }
    })
    queries = []

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |url|
      query = URI.decode_www_form(URI.parse(url).query).to_h.fetch("q")
      queries << query
      { "items" => [] }
    })

    assert_equal "no_match", metadata.dig("enrichment", "status")
    assert_includes queries, "intitle:A Century of Profitable Industry Trends inauthor:Carlo Zarattini"
    assert_includes queries, "intitle:A Century of Profitable Industry Trends inauthor:Gary Antonacci"
    assert_includes queries, "intitle:A Century of Profitable Industry Trends inpublisher:Wiley"
    assert_equal queries, metadata.dig("enrichment", "queries")
  end

  test "retombe sur le titre lorsque la recherche ISBN ne renvoie rien" do
    document = document_with_filename("causal-factor-investing.pdf")
    document.update!(metadata: {
      "bibliography" => { "title" => "Causal Factor Investing", "identifiers" => { "isbn13" => [ "978-1-00939-7292" ] } }
    })
    queries = []

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |url|
      query = URI.decode_www_form(URI.parse(url).query).to_h.fetch("q")
      queries << query
      query.start_with?("isbn:") ? { "items" => [] } : { "items" => [ volume("causal-1", "Causal Factor Investing") ] }
    })

    assert_equal "accepted", metadata.dig("enrichment", "status")
    assert_includes queries, "isbn:9781009397292"
    assert queries.any? { |query| query.start_with?("intitle:Causal Factor Investing") }
  end

  test "fusionne les champs lorsqu'un même volume est retrouvé par plusieurs requêtes" do
    document = document_with_filename("source.pdf")
    document.update!(metadata: {
      "bibliography" => {
        "title" => "Causal Factor Investing",
        "authors" => [ "Marcos M. López de Prado" ],
        "publisher" => "Cambridge University Press",
        "publication_year" => "2023"
      }
    })
    calls = 0

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      calls += 1
      if calls == 1
        { "items" => [ { "id" => "same", "volumeInfo" => { "title" => "Causal Factor Investing" } } ] }
      else
        { "items" => [ volume("same", "Causal Factor Investing") ] }
      end
    })

    candidate = metadata.dig("enrichment", "candidates").find { |entry| entry["volume_id"] == "same" }
    assert_equal [ "Marcos M. López de Prado" ], candidate["authors"]
    assert_equal "Cambridge University Press", candidate["publisher"]
    assert_equal "2023-10-31", candidate["published_date"]
    assert_operator candidate.dig("matching", "score"), :>=, 0.72
  end

  test "ne promeut pas un ISBN exact dont le titre est contradictoire" do
    document = document_with_filename("source.pdf")
    document.update!(metadata: {
      "bibliography" => { "title" => "Ouvrage sans rapport", "identifiers" => { "isbn13" => [ "978-1-00939-7292" ] } }
    })

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ volume("wrong", "Causal Factor Investing") ] }
    })

    assert_equal "no_match", metadata.dig("enrichment", "status")
    assert_nil metadata.dig("enrichment", "volume_id")
  end

  test "conserve et vérifie un ISSN retourné par Google Books" do
    document = document_with_filename("magazine.pdf")
    document.update!(metadata: {
      "bibliography" => { "title" => "Revue quantitative", "identifiers" => { "issn" => [ "2049-3630" ] } }
    })
    item = volume("magazine-1", "Revue quantitative")
    item["volumeInfo"]["industryIdentifiers"] = [ { "type" => "ISSN", "identifier" => "2049-3630" } ]

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |url|
      query = URI.decode_www_form(URI.parse(url).query).to_h.fetch("q")
      query.start_with?("issn:") ? { "items" => [ item ] } : { "items" => [] }
    })

    assert_equal "accepted", metadata.dig("enrichment", "status")
    assert_equal [ "20493630" ], metadata.dig("bibliography", "identifiers", "issn")
  end

  test "ne convertit pas un ISBN 979 en ISBN-10 équivalent" do
    document = document_with_filename("target.pdf")
    document.update!(metadata: {
      "bibliography" => { "title" => "Target", "identifiers" => { "isbn13" => [ "9791234567896" ] } }
    })
    item = volume("wrong-edition", "Target")
    item["volumeInfo"]["industryIdentifiers"] = [ { "type" => "ISBN_10", "identifier" => "123456789X" } ]

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ item ] }
    })

    assert_equal "review_required", metadata.dig("enrichment", "status")
  end

  test "omet une note Google Books hors limites" do
    document = document_with_filename("rating.pdf")
    item = volume("bad-rating", "Rating")
    item["volumeInfo"].update("averageRating" => 6, "ratingsCount" => -1)

    metadata = GoogleBooksMetadataEnricher.call(document, api_key: "secret-test", transport: lambda { |_url|
      { "items" => [ item ] }
    })

    assert_nil metadata.dig("enrichment", "candidates", 0, "rating")
  end

  private

  def document_with_filename(filename)
    document = Document.create!(source_sha256: SecureRandom.hex(32))
    document.source_pdf.attach(io: StringIO.new("%PDF-test"), filename: filename, content_type: "application/pdf")
    document
  end

  def volume(id, title)
    {
      "id" => id,
      "volumeInfo" => {
        "title" => title,
        "authors" => [ "Marcos M. López de Prado" ],
        "publisher" => "Cambridge University Press",
        "publishedDate" => "2023-10-31",
        "language" => "en",
        "industryIdentifiers" => [ { "type" => "ISBN_13", "identifier" => "9781009397292" } ],
        "averageRating" => 4.5,
        "ratingsCount" => 20
      }
    }
  end
end
