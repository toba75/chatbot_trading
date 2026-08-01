require "test_helper"

class DocumentsControllerTest < ActionDispatch::IntegrationTest
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"

  test "liste les documents courants du plus récent au plus ancien" do
    legacy, = create_document_with_attempt
    legacy.update_column(:created_at, 3.hours.ago)
    retried, = create_document_with_attempt
    retried.update!(retried_from: legacy, created_at: 2.hours.ago)
    retried.current_attempt.update!(status: "succeeded")
    independent, = create_document_with_attempt
    independent.update_column(:created_at, 1.hour.ago)

    get documents_path

    assert_response :success
    assert_select %(main[data-controller="cable-reconcile"][data-cable-reconcile-url-value="#{documents_path}"])
    assert_select %(turbo-frame#documents_index[data-cable-reconcile-target="frame"][target="_top"])
    assert_select "turbo-cable-stream-source", count: 2
    links = css_select(".document-list a.document-link").map { |link| link["href"] }
    assert_equal [ document_path(independent), document_path(retried) ], links
    assert_select "a[href='#{root_path}']", text: "Nouveau document"
  end

  test "dépose le PDF et programme sa première tentative sans l'exécuter" do
    assert_difference -> { Document.count }, 1 do
      assert_difference -> { ConversionAttempt.count }, 1 do
        assert_difference -> { conversion_jobs.count }, 1 do
          post documents_path, params: { document: { source_pdf: uploaded_file } }
        end
      end
    end

    document = Document.order(:id).last
    assert_redirected_to document_path(document)
    assert_predicate document.current_attempt, :queued?
  end

  test "ne persiste rien lorsque le fichier n'est pas un PDF" do
    invalid = Tempfile.new([ "invalid", ".pdf" ])
    invalid.write("texte")
    invalid.rewind

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_no_difference -> { SolidQueue::Job.count } do
          post documents_path, params: {
            document: { source_pdf: fixture_file_upload(invalid.path, "application/pdf", true) }
          }
        end
      end
    end

    assert_response :unprocessable_content
    assert_includes response.body, "signature d’un PDF"
  ensure
    invalid.close!
  end

  test "annule le document et la tentative si la mise en file échoue" do
    original = ConvertDocumentJob.method(:perform_later)
    ConvertDocumentJob.define_singleton_method(:perform_later) { |_| raise ActiveJob::EnqueueError, "queue indisponible" }

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_raises(ActiveJob::EnqueueError) do
          post documents_path, params: { document: { source_pdf: uploaded_file } }
        end
      end
    end
  ensure
    ConvertDocumentJob.define_singleton_method(:perform_later, original)
  end

  test "place l'abonnement Cable hors du contenu réconcilié" do
    document, attempt = create_document_with_attempt

    get document_path(document)

    assert_response :success
    stream = response.body.index("turbo-cable-stream-source")
    frame = response.body.index("<turbo-frame")
    assert stream
    assert frame
    assert_operator stream, :<, frame
    assert_select %(main[data-controller="cable-reconcile"])
    assert_select %(turbo-frame#document_#{document.id})
    assert_select %(time[data-controller="elapsed-time"][data-elapsed-time-started-at-value="#{attempt.created_at.iso8601}"])
  end

  test "relance le même document sans écraser la tentative ni ses sorties" do
    document, failed_attempt = failed_document

    get document_path(document)
    assert_select "a", text: "Réponse Docling brute"
    assert_select %(form[action="/documents/#{document.id}/retry"])
    assert_select %(time[data-elapsed-time-ended-at-value="#{failed_attempt.completed_at.iso8601}"])

    assert_no_difference -> { Document.count } do
      assert_difference -> { document.conversion_attempts.count }, 1 do
        assert_difference -> { conversion_jobs.count }, 1 do
          post "/documents/#{document.id}/retry"
        end
      end
    end

    retry_attempt = document.reload.current_attempt
    assert_redirected_to document_path(document)
    assert_predicate retry_attempt, :queued?
    assert_equal 86_400, retry_attempt.conversion_options.fetch("document_timeout")
    assert_equal "réponse en échec".b, failed_attempt.docling_response.download

    get document_path(document)
    assert_select "details.attempt-history"
    assert_select "a", text: "Réponse Docling brute"
    assert_select "code", text: "conversion_failed"
  end

  test "refuse de relancer un document qui n'est pas en échec" do
    document, = create_document_with_attempt

    assert_no_difference -> { document.conversion_attempts.count } do
      assert_no_difference -> { SolidQueue::Job.count } do
        post "/documents/#{document.id}/retry"
      end
    end

    assert_response :conflict
  end

  test "affiche le PDF, l'HTML confiné, le Markdown brut et les cinq pages" do
    document, = completed_document

    get document_path(document)

    assert_response :success
    assert_select %(iframe[title="PDF original"])
    assert_select %(iframe[title="Conversion HTML"][sandbox=""])
    assert_select "pre", text: "<script>résumé</script>"
    assert_select "li", text: /Page 5.+vide/
    assert_match(/2 images.+pages 2 et 3/m, response.body)
  end

  test "sert l'HTML exact avec une politique de confinement" do
    document, = completed_document

    get html_preview_document_path(document)

    assert_response :success
    assert_equal %(<html><body><a href="javascript:alert(1)">conversion</a></body></html>), response.body
    assert_equal "nosniff", response.headers.fetch("X-Content-Type-Options")
    assert_includes response.headers.fetch("Content-Security-Policy"), "sandbox"
    assert_includes response.headers.fetch("Content-Security-Policy"), "img-src data:"
  end

  test "affiche la progression puis le verdict et les preuves de la qualification" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.update!(
      status: "running",
      phase: "candidate_evaluation",
      completed_units: 3,
      total_units: 5,
      execution_job_id: "qualification-en-cours",
      started_at: Time.current
    )

    get document_path(document)

    assert_select "h2", text: "Qualification mathématique"
    assert_select %(progress[value="3"][max="5"])

    qualification.update!(
      status: "succeeded",
      phase: "persisting_result",
      completed_units: 1,
      total_units: 1,
      verdict: "partial",
      summary: {
        "regions" => 5,
        "conformant" => 3,
        "contradicted" => 0,
        "non_verifiable" => 2,
        "coverage" => { "pages_total" => 2, "pages_traced" => 1 },
        "region_details" => [
          { "id" => "r1", "page" => 1, "bbox" => [ 1, 2, 3, 4 ], "verdict" => "partial", "reasons" => [] }
        ],
        "page_exclusions" => [
          { "page" => 2, "status" => "unsupported", "reasons" => [ { "message" => "Police non supportée" } ] }
        ]
      },
      completed_at: Time.current
    )
    {
      report: [ "{}", "report.json", "application/json" ],
      source_evidence: [ "preuve", "evidence.ndjson.gz", "application/gzip" ],
      analyzer_response: [ "flux", "response.ndjson", "application/x-ndjson" ]
    }.each do |name, (content, filename, content_type)|
      qualification.public_send(name).attach(
        io: StringIO.new(content),
        filename: filename,
        content_type: content_type
      )
    end

    get document_path(document)

    assert_select ".math-verdict", text: /partial/
    assert_select ".math-summary dd", text: "5"
    assert_select ".math-regions td", text: "1, 2, 3, 4"
    assert_select "li", text: /Police non supportée/
    assert_select "a", text: "Rapport de qualification"
    assert_select "a", text: "Preuve source"
    assert_select "a", text: "Réponse brute de l’analyseur"
  end

  private

  def conversion_jobs
    SolidQueue::Job.where(queue_name: "conversions")
  end

  def uploaded_file
    fixture_file_upload(REFERENCE_PDF, "application/pdf", true)
  end

  def create_document_with_attempt
    document = Document.create_from_pdf!(uploaded_file)
    attempt = document.start_conversion!(conversion_options: DoclingClient.conversion_options)
    [ document, attempt ]
  end

  def completed_document
    document, attempt = create_document_with_attempt
    json = {
      "pages" => (1..5).to_h { |page| [ page.to_s, { "page_no" => page } ] },
      "texts" => (1..4).map { |page| { "prov" => [ { "page_no" => page } ] } },
      "tables" => [],
      "pictures" => [
        { "prov" => [ { "page_no" => 2 } ] },
        { "prov" => [ { "page_no" => 3 } ] }
      ]
    }
    {
      docling_document: [ JSON.generate(json), "document.json", "application/json" ],
      html: [ %(<html><body><a href="javascript:alert(1)">conversion</a></body></html>), "document.html", "text/html" ],
      markdown: [ "<script>résumé</script>", "document.md", "text/markdown" ]
    }.each do |name, (content, filename, content_type)|
      attempt.public_send(name).attach(io: StringIO.new(content), filename: filename, content_type: content_type)
    end
    attempt.update!(status: "succeeded", page_count: 5, completed_at: Time.current)
    [ document, attempt ]
  end

  def failed_document
    document, attempt = create_document_with_attempt
    attempt.docling_response.attach(
      io: StringIO.new("réponse en échec"),
      filename: "response.json",
      content_type: "application/json"
    )
    attempt.update!(status: "failed", error_code: "conversion_failed", completed_at: Time.current)
    [ document, attempt ]
  end
end
