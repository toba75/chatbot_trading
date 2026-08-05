require "test_helper"
require "securerandom"

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

  test "liste une qualification échouée sans déclarer le document terminé" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    qualification.update!(
      status: "failed",
      error_code: "analysis_failed",
      error_message: "Analyse impossible.",
      completed_at: Time.current
    )

    get documents_path

    assert_response :success
    assert_select ".status-badge--qualification_failed", text: "Échec qualification"
    assert_select ".status-badge--completed", text: "Terminé", count: 0
    assert_select "a[href='#{document_path(document)}']"
  end

  test "dépose le PDF et programme sa première tentative sans l'exécuter" do
    assert_difference -> { Document.count }, 1 do
      assert_difference -> { ConversionAttempt.count }, 1 do
        assert_difference -> { conversion_jobs.count }, 1 do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file ] } }
        end
      end
    end

    document = Document.order(:id).last
    assert_redirected_to documents_path
    assert_predicate document.current_attempt, :queued?
  end

  test "programme la conversion seulement lorsque le fichier source est lisible" do
    original = ConvertDocumentJob.method(:perform_later)
    storage_ready = []
    ConvertDocumentJob.define_singleton_method(:perform_later) do |attempt|
      blob = attempt.document.source_pdf.blob
      storage_ready << blob.service.exist?(blob.key)
      original.call(attempt)
    end

    post documents_path, params: { document: { source_pdfs: [ uploaded_file ] } }

    assert_redirected_to documents_path
    assert_equal [ true ], storage_ready
  ensure
    ConvertDocumentJob.define_singleton_method(:perform_later, original)
  end

  test "dépose plusieurs PDFs et programme une tentative par document" do
    assert_difference -> { Document.count }, 2 do
      assert_difference -> { ConversionAttempt.count }, 2 do
        assert_difference -> { conversion_jobs.count }, 2 do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file, unique_uploaded_file ] } }
        end
      end
    end

    assert_redirected_to documents_path
    assert_equal [ true, true ], Document.order(:id).last(2).map { |document| document.current_attempt.queued? }
  end

  test "ignore un PDF déjà importé même si le nom diffère" do
    create_document_with_attempt(uploaded_file(filename: "original.pdf"))

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file(filename: "copie.pdf") ] } }
        end
      end
    end

    assert_redirected_to documents_path
    assert_equal "copie.pdf a déjà été importé.", flash[:alert]
  end

  test "importe les PDF nouveaux et signale les doublons du même lot" do
    assert_difference -> { Document.count }, 1 do
      assert_difference -> { ConversionAttempt.count }, 1 do
        assert_difference -> { conversion_jobs.count }, 1 do
          post documents_path, params: {
            document: { source_pdfs: [ uploaded_file(filename: "original.pdf"), uploaded_file(filename: "copie.pdf") ] }
          }
        end
      end
    end

    assert_redirected_to documents_path
    assert_equal "copie.pdf a déjà été importé.", flash[:alert]
  end

  test "ne persiste rien lorsque le fichier n'est pas un PDF" do
    invalid = Tempfile.new([ "invalid", ".pdf" ])
    invalid.write("texte")
    invalid.rewind

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: {
            document: { source_pdfs: [ fixture_file_upload(invalid.path, "application/pdf", true) ] }
          }
        end
      end
    end

    assert_response :unprocessable_content
    assert_includes response.body, "signature d’un PDF"
  ensure
    invalid.close!
  end

  test "annule tout le lot lorsqu'un des fichiers n'est pas un PDF" do
    invalid = Tempfile.new([ "invalid", ".pdf" ])
    invalid.write("texte")
    invalid.rewind

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: {
            document: {
              source_pdfs: [
                uploaded_file,
                fixture_file_upload(invalid.path, "application/pdf", true)
              ]
            }
          }
        end
      end
    end

    assert_response :unprocessable_content
    assert_includes response.body, "signature d’un PDF"
    assert_select "nav[aria-label='Navigation principale'] a[href='#{root_path}'][aria-current='page']", text: "Importer"
  ensure
    invalid.close!
  end

  test "rend visible l'échec de mise en file de conversion" do
    original = ConvertDocumentJob.method(:perform_later)
    ConvertDocumentJob.define_singleton_method(:perform_later) { |_| raise ActiveJob::EnqueueError, "queue indisponible" }

    assert_difference -> { Document.count }, 1 do
      assert_difference -> { ConversionAttempt.count }, 1 do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file ] } }
        end
      end
    end

    attempt = Document.order(:id).last.current_attempt
    assert_redirected_to documents_path
    assert_predicate attempt, :failed?
    assert_equal "enqueue_failed", attempt.error_code
    assert_equal "queue indisponible", attempt.error_message
    assert_includes flash[:alert], "n'a pas pu être mis en file de conversion"
  ensure
    ConvertDocumentJob.define_singleton_method(:perform_later, original)
  end

  test "rend visible l'échec de stockage du PDF source" do
    service = ActiveStorage::Blob.service
    original_upload = service.method(:upload)
    service.define_singleton_method(:upload) do |_key, _io, **_options|
      raise IOError, "disque plein"
    end

    assert_no_difference -> { Document.count } do
      assert_no_difference -> { ConversionAttempt.count } do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file ] } }
        end
      end
    end

    assert_redirected_to documents_path
    assert_includes flash[:alert], "n'a pas pu être stocké sur la machine hôte"
  ensure
    service.define_singleton_method(:upload, original_upload) if service && original_upload
  end

  test "rend visible une mise en file de conversion refusée sans exception" do
    original = ConvertDocumentJob.method(:perform_later)
    ConvertDocumentJob.define_singleton_method(:perform_later) { |_| false }

    assert_difference -> { Document.count }, 1 do
      assert_difference -> { ConversionAttempt.count }, 1 do
        assert_no_difference -> { conversion_jobs.count } do
          post documents_path, params: { document: { source_pdfs: [ uploaded_file ] } }
        end
      end
    end

    attempt = Document.order(:id).last.current_attempt
    assert_redirected_to documents_path
    assert_predicate attempt, :failed?
    assert_equal "enqueue_failed", attempt.error_code
    assert_equal "Solid Queue a refusé le job de conversion.", attempt.error_message
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
    assert_select "a[href='#{root_path}']", text: "Nouveau document", count: 0
    assert_select "a[href='#{documents_path}'][data-turbo-frame='_top']", text: "Documents"
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

  test "affiche le PDF et un seul format Docling sélectionnable par onglets" do
    document, = completed_document

    get document_path(document)

    assert_response :success
    assert_select %(section[data-controller="page-sync"])
    assert_select %(canvas[title="Page courante du PDF original"])
    assert_select %(nav[aria-label="Navigation dans le PDF original"] input[value="1"])
    assert_select %(nav[aria-label="Formats Docling"] a[role="tab"]), count: 5
    assert_select %(a[role="tab"][hidden]), text: "HTML corrigé"
    assert_select %(a[role="tab"][hidden]), text: "HTML natif paginé"
    assert_select %(a[role="tab"][href="#{docling_page_preview_document_path(document, page: 1)}"]), text: "JSON"
    assert_select %(a[role="tab"][aria-selected="true"]), text: "HTML natif exact"
    assert_select %(section[data-page-sync-html-synchronized-value="false"])
    assert_select %(a[data-page-sync-target~="htmlTab"][href="#{html_preview_document_path(document)}"]), text: "HTML natif exact"
    assert_select %(iframe[title="HTML natif exact"][sandbox=""]), count: 1
    assert_select %(iframe[src="#{html_preview_document_path(document)}"]), count: 1
    assert_select %([data-page-sync-target="htmlSyncNotice"]), text: /synchronisation HTML par page/
    assert_not_includes response.body, "&lt;script&gt;résumé&lt;/script&gt;"
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

  test "affiche et sert la vue HTML native paginée quand elle est disponible" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    page_html = "<html><body><div class='page' id='page-1'>conversion</div></body></html>"
    qualification.native_page_html.attach(
      io: StringIO.new(page_html), filename: "native-page.html", content_type: "text/html"
    )
    qualification.update!(
      status: "succeeded", phase: "persisting_result", completed_units: 1,
      total_units: 1, verdict: "conformant_within_scope",
      summary: {
        "regions" => 0, "conformant" => 0, "contradicted" => 0, "non_verifiable" => 0,
        "coverage" => { "pages_total" => 1, "pages_traced" => 1 },
        "correction" => { "status" => "not_required", "targets" => 0, "accepted" => 0, "rejected" => 0, "failed" => 0 },
        "region_details" => [], "page_exclusions" => []
      },
      completed_at: Time.current
    )

    get document_path(document)

    assert_select %(section[data-page-sync-html-url-value="#{page_html_preview_document_path(document)}"])
    assert_select %(section[data-page-sync-html-synchronized-value="true"])
    assert_select %([data-controller="page-html-availability"][data-page-html-availability-url-value="#{page_html_preview_document_path(document)}"][data-page-html-availability-label-value="HTML natif paginé"][data-page-html-availability-corrected-value="false"])
    assert_select %(iframe[src="#{page_html_preview_document_path(document)}#page-1"])
    assert_select %([data-page-sync-target="htmlSyncNotice"][hidden])

    get page_html_preview_document_path(document)

    assert_response :success
    assert_equal page_html.b, response.body
    assert_includes response.headers.fetch("Content-Security-Policy"), "sandbox"
  end

  test "sert le Markdown brut à la demande" do
    document, = completed_document

    get markdown_preview_document_path(document)

    assert_redirected_to rails_blob_path(document.current_attempt.markdown, disposition: "inline")
    assert_equal "text/markdown", document.current_attempt.markdown.content_type
  end

  test "sert uniquement la projection JSON de la page demandée" do
    document, attempt = completed_document
    link = {
      "id" => "pdf-source:2:4",
      "page" => 2,
      "source_bbox" => [ 10, 20, 30, 40 ],
      "docling_ref" => "#/texts/1",
      "docling_charspan" => [ 0, 4 ],
      "docling_text" => "page",
      "link_status" => "linked"
    }
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    qualification.update!(
      status: "succeeded",
      phase: "persisting_result",
      completed_units: 1,
      total_units: 1,
      verdict: "partial",
      summary: { "region_details" => [ link ] },
      completed_at: Time.current
    )

    get docling_page_preview_document_path(document, page: 2)

    assert_response :success
    assert_equal "application/json", response.media_type
    projection = JSON.parse(response.body)
    assert_equal 2, projection.dig("_projection", "page_no")
    assert_equal 2, projection.dig("page", "page_no")
    assert_equal [ link ], projection.fetch("_math_links")
    assert_equal [ 2 ], projection.fetch("pictures").flat_map { |picture| picture.fetch("prov").pluck("page_no") }
    assert_equal [ 2 ], projection.fetch("texts").flat_map { |text| text.fetch("prov").pluck("page_no") }
  end

  test "refuse un numéro de page invalide ou absent" do
    document, = completed_document

    get docling_page_preview_document_path(document, page: "deux")
    assert_response :unprocessable_content

    get docling_page_preview_document_path(document, page: 8)
    assert_response :not_found
  end

  test "affiche l'HTML corrigé paginé à côté de l'HTML natif" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    derived_html = %(<script>alert("interdit")</script><div class="page" id="page-1"><math><mi>x</mi></math></div>)
    qualification.derived_html.attach(
      io: StringIO.new(derived_html),
      filename: "derived.html",
      content_type: "text/html"
    )
    qualification.native_page_html.attach(
      io: StringIO.new("<div class='page' id='page-1'>natif</div>"),
      filename: "native-page.html",
      content_type: "text/html"
    )
    qualification.update!(
      status: "succeeded",
      phase: "persisting_result",
      completed_units: 1,
      total_units: 1,
      verdict: "contradicted",
      summary: {
        "regions" => 1, "conformant" => 0, "contradicted" => 1, "non_verifiable" => 0,
        "coverage" => { "pages_total" => 1, "pages_traced" => 1 },
        "correction" => { "status" => "corrected", "targets" => 1, "accepted" => 1, "rejected" => 0, "failed" => 0 },
        "region_details" => [], "page_exclusions" => []
      },
      completed_at: Time.current
    )

    get document_path(document)

    assert_select %(nav[aria-label="Formats Docling"] a[role="tab"]), count: 5
    assert_select %(a[data-page-sync-target~="htmlTab"]), count: 3
    assert_select %(a[aria-selected="true"][href="#{derived_html_preview_document_path(document)}"]), text: "HTML corrigé"
    assert_select %(a[href="#{page_html_preview_document_path(document)}"]), text: "HTML natif paginé"
    assert_select %(a[href="#{html_preview_document_path(document)}"]), text: "HTML natif exact"
    assert_select %([data-page-html-availability-corrected-value="true"])
    assert_select %(iframe[src="#{derived_html_preview_document_path(document)}#page-1"]), count: 1
    assert_select ".math-correction", text: /onglet « HTML corrigé »/
    assert_select "iframe.conversion-preview", count: 0

    get derived_html_preview_document_path(document)

    assert_response :success
    assert_equal derived_html.b, response.body
    assert_equal "text/html", response.media_type
    assert_match(/\Ainline\b/, response.headers.fetch("Content-Disposition"))
    assert_includes response.headers.fetch("Content-Security-Policy"), "sandbox"
    assert_equal "nosniff", response.headers.fetch("X-Content-Type-Options")
  end

  test "affiche la progression puis le verdict et les preuves de la qualification" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
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
        "correction" => {
          "status" => "not_required", "targets" => 0, "accepted" => 0,
          "rejected" => 0, "failed" => 0
        },
        "region_details" => [
          { "id" => "r1", "page" => 1, "bbox" => [ 1, 2, 3, 4 ], "verdict" => "partial", "reasons" => [] }
        ],
        "page_exclusions" => [
          { "page" => 2, "status" => "unsupported", "reasons" => [ { "message" => "Police non supportée" } ] }
        ]
      },
      completed_at: Time.current
    )

    get document_path(document)

    assert_select ".math-verdict", text: /partial/
    assert_select ".math-summary dd", text: "5"
    assert_select ".math-regions td", text: "1, 2, 3, 4"
    assert_select "li", text: /Police non supportée/
    assert_select "a", text: "Rapport de qualification"
    assert_select "a", text: "Preuve source"
    assert_select "a", text: "Réponse brute de l’analyseur"
  end

  test "affiche une qualification historique sans exiger le résumé de correction" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    legacy_identity = [
      qualification.source_sha256,
      qualification.docling_document_sha256,
      "1.0",
      "0.4.0",
      "pdf-docling-semantic-v1"
    ].join(":")
    qualification.update_columns(
      contract_version: "1.0",
      analyzer_version: "0.4.0",
      capability_profile: "pdf-docling-semantic-v1",
      input_fingerprint: Digest::SHA256.hexdigest(legacy_identity),
      status: "succeeded",
      phase: "persisting_result",
      completed_units: 1,
      total_units: 1,
      verdict: "conformant_within_scope",
      summary: {
        "regions" => 0,
        "conformant" => 0,
        "contradicted" => 0,
        "non_verifiable" => 0,
        "coverage" => { "pages_total" => 1, "pages_traced" => 1 },
        "region_details" => [],
        "page_exclusions" => []
      },
      completed_at: Time.current
    )

    get document_path(document)

    assert_response :success
    assert_select "p", text: "Qualification historique sans phase de correction automatique."
    assert_select "form[action='#{retry_math_qualification_document_path(document)}']", text: /Requalifier/
  end

  test "affiche et exécute la relance d'une qualification courante en développement" do
    document, attempt = completed_document
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    qualification.save!
    qualification.update!(
      status: "succeeded", phase: "persisting_result", completed_units: 1,
      total_units: 1, verdict: "conformant_within_scope", completed_at: Time.current,
      summary: {
        "regions" => 0, "conformant" => 0, "contradicted" => 0,
        "non_verifiable" => 0,
        "coverage" => { "pages_total" => 5, "pages_traced" => 5 },
        "region_details" => [], "page_exclusions" => []
      }
    )

    with_current_math_requalification do
      get document_path(document)
      assert_select "form[action='#{retry_math_qualification_document_path(document)}']",
        text: /Relancer l’analyse et les corrections/

      assert_difference -> { attempt.math_qualifications.count }, 1 do
        assert_difference -> { math_qualification_jobs.count }, 1 do
          post retry_math_qualification_document_path(document)
        end
      end
    end

    assert_redirected_to document_path(document)
    assert_predicate attempt.reload.current_math_qualification, :queued?
  end

  test "relance seulement la qualification et conserve l'échec précédent" do
    document, attempt = completed_document
    failed = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    failed.save!
    failed.analyzer_response.attach(
      io: StringIO.new("preuve de l’échec"),
      filename: "response.ndjson",
      content_type: "application/x-ndjson"
    )
    failed.update!(
      status: "failed",
      error_code: "analysis_failed",
      error_message: "Traceback (most recent call last): chemin interne",
      completed_at: Time.current
    )

    assert_no_difference -> { attempt.document.conversion_attempts.count } do
      assert_difference -> { attempt.math_qualifications.count }, 1 do
        assert_difference -> { math_qualification_jobs.count }, 1 do
          post retry_math_qualification_document_path(document)
        end
      end
    end

    current = attempt.reload.current_math_qualification
    assert_redirected_to document_path(document)
    assert_predicate current, :queued?
    assert_equal failed.docling_document_sha256, current.docling_document_sha256
    assert_equal "preuve de l’échec".b, failed.analyzer_response.download

    get document_path(document)

    assert_select "section#math_qualification", text: /En attente/
    assert_select "details.math-qualification-history"
    assert_select "h3", text: /— échec/
    assert_select "p", text: /La qualification a échoué/
    assert_no_match(/Traceback|chemin interne/, response.body)
    assert_select "code", text: "analysis_failed"
    assert_select "a", text: "Réponse brute de l’analyseur"
  end

  test "refuse de relancer une qualification encore en attente" do
    document, attempt = completed_document
    MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    ).save!

    assert_no_difference -> { attempt.math_qualifications.count } do
      assert_no_difference -> { math_qualification_jobs.count } do
        post retry_math_qualification_document_path(document)
      end
    end

    assert_response :conflict
  end

  test "rend visible un échec de mise en file de la relance" do
    document, attempt = completed_document
    failed = MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    )
    failed.update!(status: "failed", completed_at: Time.current)

    original = QualifyMathJob.method(:perform_later)
    QualifyMathJob.define_singleton_method(:perform_later) do |_qualification|
      raise SolidQueue::Job::EnqueueError, "base indisponible"
    end
    begin
      assert_no_difference -> { math_qualification_jobs.count } do
        post retry_math_qualification_document_path(document)
      end
    ensure
      QualifyMathJob.define_singleton_method(:perform_later, original)
    end

    current = attempt.reload.current_math_qualification
    assert_redirected_to document_path(document)
    assert_predicate current, :failed?
    assert_equal "enqueue_failed", current.error_code
    assert_equal "base indisponible", current.error_message
  end

  private

  def conversion_jobs
    SolidQueue::Job.where(queue_name: "conversions")
  end

  def math_qualification_jobs
    SolidQueue::Job.where(queue_name: "math_qualifications")
  end

  def uploaded_file(filename: File.basename(REFERENCE_PDF))
    Rack::Test::UploadedFile.new(REFERENCE_PDF, "application/pdf", true, original_filename: filename)
  end

  def unique_uploaded_file(filename: "document-#{SecureRandom.hex(4)}.pdf")
    file = Tempfile.new([ "document", ".pdf" ])
    file.binmode
    file.write("%PDF-#{SecureRandom.uuid}")
    file.rewind
    (@uploaded_tempfiles ||= []) << file

    Rack::Test::UploadedFile.new(file.path, "application/pdf", true, original_filename: filename)
  end

  def create_document_with_attempt(upload = unique_uploaded_file)
    document = Document.create_from_pdf!(upload)
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
