require "test_helper"

class QualifyMathJobTest < ActiveJob::TestCase
  test "persiste la progression, les preuves et un verdict contradictoire" do
    qualification = create_qualification
    client = FakeClient.new(successful_result)
    source_before = qualification.conversion_attempt.document.source_pdf.download
    document_before = qualification.conversion_attempt.docling_document.download

    job_with(client).perform(qualification)

    qualification.reload
    assert_predicate qualification, :succeeded?
    assert_predicate qualification, :contradicted?
    assert_equal "persisting_result", qualification.phase
    assert_equal 1, qualification.completed_units
    assert_equal 1, qualification.total_units
    assert_equal 2, qualification.summary.fetch("regions")
    assert_equal 1, qualification.summary.fetch("conformant")
    assert_equal 1, qualification.summary.fetch("contradicted")
    assert_equal 0, qualification.summary.fetch("non_verifiable")
    assert_equal 1, qualification.summary.dig("coverage", "pages_total")
    assert_equal 2, qualification.summary.fetch("region_details").size
    assert_equal [], qualification.summary.fetch("page_exclusions")
    assert_equal successful_result.raw_response.b, qualification.analyzer_response.download
    assert_equal successful_result.report_bytes.b, qualification.report.download
    assert_equal successful_result.evidence.b, qualification.source_evidence.download
    assert_equal "rejected", qualification.summary.dig("correction", "status")
    assert_equal "rejected", JSON.parse(qualification.corrections.download).dig("records", 0, "status")
    assert_equal "PK", qualification.correction_evidence.download
    assert_equal successful_result.native_page_html.b, qualification.native_page_html.download
    assert qualification.started_at
    assert qualification.completed_at
    assert_equal source_before, qualification.conversion_attempt.document.source_pdf.download
    assert_equal document_before, qualification.conversion_attempt.docling_document.download
  end

  test "persiste séparément le document et les exports corrigés" do
    qualification = create_qualification
    result = successful_result(corrected: true)

    job_with(FakeClient.new(result)).perform(qualification)

    qualification.reload
    assert_equal "corrected", qualification.summary.dig("correction", "status")
    assert_equal "DoclingDocument", JSON.parse(qualification.derived_docling_document.download).fetch("schema_name")
    assert_equal result.derived_html.b, qualification.derived_html.download
    assert_includes qualification.derived_html.download, "id='page-1'"
    assert_includes qualification.derived_html.download, "<math "
    assert_equal "$x$".b, qualification.derived_markdown.download
    assert_equal '{"schema_name":"DoclingDocument","texts":[{"text":"autre"},{"text":"x"}],"pages":{"1":{}}}', qualification.conversion_attempt.docling_document.download
  end

  test "publie les zones opaques sans exclure toute la page" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_traced_with_exclusions" => 1
    )
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "traced_with_exclusions",
        "opaque_regions" => [
          {
            "kind" => "form_xobject",
            "resource" => "/X1",
            "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
            "reason" => {
              "code" => "form_xobject_vector_content_unqualified",
              "message" => "Contenu vectoriel non qualifié"
            }
          },
          {
            "kind" => "image_xobject",
            "resource" => "/X2",
            "bbox" => [ 40.0, 50.0, 60.0, 70.0 ],
            "reason" => {
              "code" => "image_xobject_content_unqualified",
              "message" => "Contenu matriciel non qualifié"
            }
          }
        ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    exclusion = qualification.reload.summary.fetch("page_exclusions").sole
    assert_equal "traced_with_exclusions", exclusion.fetch("status")
    assert_equal [ 10.0, 20.0, 30.0, 40.0 ], exclusion.dig("regions", 0, "bbox")
    assert_equal "image_xobject", exclusion.dig("regions", 1, "kind")
    assert_equal 1, qualification.summary.dig("coverage", "pages_traced_with_exclusions")
  end

  test "refuse des compteurs de pages qui contredisent leurs statuts" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_traced_with_exclusions" => 1
    )

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une zone opaque sur une page déclarée entièrement tracée" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("pages").first["opaque_regions"] = [
      {
        "kind" => "image_xobject",
        "resource" => "/Im1",
        "bbox" => [ 1.0, 1.0, 2.0, 2.0 ],
        "reason" => {
          "code" => "image_xobject_content_unqualified",
          "message" => "Contenu matriciel non qualifié"
        }
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une zone opaque incomplète avant sa persistance" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_traced_with_exclusions" => 1
    )
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "traced_with_exclusions",
        "opaque_regions" => [
          {
            "kind" => "form_xobject",
            "resource" => "/X1",
            "reason" => {
              "code" => "form_xobject_vector_content_unqualified",
              "message" => "Contenu vectoriel non qualifié"
            }
          }
        ]
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "conserve les artefacts partiels et rend l'échec visible" do
    qualification = create_qualification
    partial = MathQualificationClient::Result.new(
      raw_response: "flux partiel\n",
      report: nil,
      report_bytes: "",
      evidence: "preuve partielle",
      corrections: "",
      correction_evidence: "",
      derived_docling_document: "",
      derived_html: "",
      derived_markdown: "",
      native_page_html: ""
    )
    error = MathQualificationClient::QualificationError.new(
      "analysis_failed",
      "Analyse impossible.",
      result: partial
    )

    assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(error: error)).perform(qualification)
    end

    qualification.reload
    assert_predicate qualification, :failed?
    assert_equal "analysis_failed", qualification.error_code
    assert_equal "Analyse impossible.", qualification.error_message
    assert_equal "flux partiel\n", qualification.analyzer_response.download
    assert_equal "preuve partielle", qualification.source_evidence.download
    assert_not qualification.report.attached?
  end

  test "persiste la panne réelle de la frontière HTTP sans déclasser Docling" do
    skip "Activer avec MATH_AUDIT_FAILURE_LIVE=1" unless ENV["MATH_AUDIT_FAILURE_LIVE"] == "1"
    qualification = create_qualification

    error = assert_raises(MathQualificationClient::QualificationError) do
      QualifyMathJob.new.perform(qualification)
    end

    assert_equal "network_error", error.code
    assert_predicate qualification.reload, :failed?
    assert_equal "network_error", qualification.error_code
    assert_predicate qualification.conversion_attempt.reload, :succeeded?
    assert_not qualification.analyzer_response.attached?
    assert_not qualification.source_evidence.attached?
    assert_not qualification.report.attached?
  end

  test "refuse un rapport qui ne correspond pas aux entrées de la qualification" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("contract")["source_sha256"] = "f" * 64

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un total de régions qui contredit le détail du rapport" do
    qualification = create_qualification
    result = successful_result
    result.report.dig("alignment", "evaluation", "overall")["regions"] = 3

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse une correction dont le registre ne contient aucun record accepté" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    result.corrections.replace('{"records":[]}')
    metadata = result.report.dig("correction", "artifacts", "corrections")
    metadata["bytes"] = result.corrections.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.corrections)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un DoclingDocument dérivé qui n'applique pas la correction" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    result.derived_docling_document.replace(
      '{"schema_name":"DoclingDocument","texts":[{"text":"autre"},{"text":"x"}],"pages":{"1":{}}}'
    )
    metadata = result.report.dig("correction", "artifacts", "derived_docling_document")
    metadata["bytes"] = result.derived_docling_document.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_docling_document)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un HTML non paginé même s'il contient le MathML accepté" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    mathml = JSON.parse(result.corrections).dig("records", 0, "mathml")
    result.derived_html.replace("<html><body><p>document étranger</p><span hidden>#{mathml}</span></body></html>")
    metadata = result.report.dig("correction", "artifacts", "derived_html")
    metadata["bytes"] = result.derived_html.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_html)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un MathML HTML qui contredit le registre accepte" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    result.derived_html.sub!("<mi>x</mi>", "<mi>y</mi>")
    metadata = result.report.dig("correction", "artifacts", "derived_html")
    metadata["bytes"] = result.derived_html.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_html)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un doublon MathML hors de la page attendue" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    duplicate = '<math data-correction-id="#/texts/1"><mi>y</mi></math>'
    result.derived_html << "<aside>#{duplicate}</aside>"
    metadata = result.report.dig("correction", "artifacts", "derived_html")
    metadata["bytes"] = result.derived_html.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_html)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un identifiant MathML absent du registre" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    result.derived_html << '<aside><math data-correction-id="ghost"><mi>z</mi></math></aside>'
    metadata = result.report.dig("correction", "artifacts", "derived_html")
    metadata["bytes"] = result.derived_html.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_html)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "normalise les entités HTML du contenu sans fabriquer de délimiteurs LaTeX" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    after = %q($x'<y\_z > 0$)
    registry = JSON.parse(result.corrections)
    mathml = '<math data-correction-id="#/texts/1" xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi><mo>&lt;</mo><mi>y</mi></math>'
    registry.fetch("records").first.merge!(
      "after" => after,
      "mathml" => mathml,
      "proposal" => %q(x'<y\_z > 0),
      "source_tokens" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "proposal_tokens" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "source_signature" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "proposal_signature" => [ "x", "'", "<", "y", "_", "z", ">", "0" ]
    )
    result.corrections.replace(JSON.generate(registry))
    result.derived_docling_document.replace(
      JSON.generate("schema_name" => "DoclingDocument", "texts" => [ { "text" => "autre" }, { "text" => after } ], "pages" => { "1" => {} })
    )
    result.derived_html.replace("<div class='page' id='page-1'>#{mathml}</div>")
    result.derived_markdown.replace(%q($x'&lt;y\_z &gt; 0$))
    %w[corrections derived_docling_document derived_html derived_markdown].each do |name|
      content = result.public_send(name)
      metadata = result.report.dig("correction", "artifacts", name)
      metadata["bytes"] = content.bytesize
      metadata["sha256"] = Digest::SHA256.hexdigest(content)
    end

    job_with(FakeClient.new(result)).perform(qualification)

    assert_predicate qualification.reload, :succeeded?

    qualification = create_qualification
    result.derived_markdown.replace(%q(&#36;x'&lt;y\_z &gt; 0&#36;))
    metadata = result.report.dig("correction", "artifacts", "derived_markdown")
    metadata["bytes"] = result.derived_markdown.bytesize
    metadata["sha256"] = Digest::SHA256.hexdigest(result.derived_markdown)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end
    assert_equal "invalid_report", error.code
  end

  test "rend terminale sans l'exécuter une qualification issue d'un ancien contrat" do
    qualification = create_qualification
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
      input_fingerprint: Digest::SHA256.hexdigest(legacy_identity)
    )

    job_with(FakeClient.new(error: "ne doit pas être appelé")).perform(qualification)

    assert_predicate qualification.reload, :failed?
    assert_equal "obsolete_contract", qualification.error_code
  end

  test "rend terminale sans l'exécuter une qualification issue d'un ancien analyseur" do
    qualification = create_qualification
    legacy_identity = [
      qualification.source_sha256,
      qualification.docling_document_sha256,
      MathQualification::CONTRACT_VERSION,
      "0.5.0",
      MathQualification::CAPABILITY_PROFILE
    ].join(":")
    qualification.update_columns(
      analyzer_version: "0.5.0",
      input_fingerprint: Digest::SHA256.hexdigest(legacy_identity)
    )

    job_with(FakeClient.new(error: "ne doit pas être appelé")).perform(qualification)

    assert_predicate qualification.reload, :failed?
    assert_equal "obsolete_contract", qualification.error_code
  end

  test "refuse de rejouer une qualification terminale sans mélanger ses preuves" do
    qualification = create_qualification
    job_with(FakeClient.new(successful_result)).perform(qualification)
    original = qualification.reload.attributes.slice("status", "verdict", "summary")
    artifacts = [
      qualification.analyzer_response.download,
      qualification.source_evidence.download,
      qualification.report.download
    ]

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new(error: RuntimeError.new("ne doit pas être appelé"))).perform(qualification)
    end

    assert_equal original, qualification.reload.attributes.slice("status", "verdict", "summary")
    assert_equal artifacts, [
      qualification.analyzer_response.download,
      qualification.source_evidence.download,
      qualification.report.download
    ]
  end

  test "rend une erreur inattendue terminale et explicite" do
    qualification = create_qualification

    assert_raises(RuntimeError) do
      job_with(FakeClient.new(error: RuntimeError.new("rupture inattendue"))).perform(qualification)
    end

    assert_predicate qualification.reload, :failed?
    assert_equal "unexpected_error", qualification.error_code
    assert_equal "rupture inattendue", qualification.error_message
  end

  test "rend terminale une qualification interrompue redélivrée au même job" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    qualification.update!(
      status: "running",
      phase: "source_analysis",
      execution_job_id: job.job_id,
      started_at: 1.minute.ago
    )

    assert_raises(QualifyMathJob::InterruptedExecution) do
      job.perform(qualification)
    end

    qualification.reload
    assert_predicate qualification, :failed?
    assert_equal "interrupted_execution", qualification.error_code
    assert qualification.completed_at
  end

  test "ne prend pas la place d'un autre job de qualification actif" do
    qualification = create_qualification
    qualification.update!(
      status: "running",
      phase: "source_analysis",
      execution_job_id: "job-actif",
      started_at: 1.minute.ago
    )

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new(successful_result)).perform(qualification)
    end

    assert_predicate qualification.reload, :running?
    assert_nil qualification.completed_at
  end

  test "une ancienne analyse ne peut pas écraser un état terminal" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    qualification.update!(
      status: "failed",
      execution_job_id: job.job_id,
      error_code: "interrupted_execution",
      completed_at: Time.current
    )

    assert_raises(QualifyMathJob::InvalidState) do
      job.send(
        :persist_progress!,
        qualification,
        { "phase" => "candidate_evaluation", "completed_units" => 1, "total_units" => 1 }
      )
    end

    assert_predicate qualification.reload, :failed?
    assert_equal "interrupted_execution", qualification.error_code
  end

  private

  def job_with(client)
    QualifyMathJob.new.tap do |job|
      job.define_singleton_method(:math_qualification_client) { client }
    end
  end

  def create_qualification
    document = Document.create!(source_sha256: "a" * 64)
    document.source_pdf.attach(
      io: StringIO.new("%PDF-source"),
      filename: "source.pdf",
      content_type: "application/pdf"
    )
    attempt = document.conversion_attempts.create!(
      status: "succeeded",
      conversion_options: { "pipeline" => "vlm" }
    )
    attempt.docling_document.attach(
      io: StringIO.new('{"schema_name":"DoclingDocument","texts":[{"text":"autre"},{"text":"x"}],"pages":{"1":{}}}'),
      filename: "document.json",
      content_type: "application/json"
    )
    MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    ).tap(&:save!)
  end

  def successful_result(corrected: false)
    qualification = MathQualification.last
    correction_status = corrected ? "accepted" : "rejected"
    counts = {
      "status" => corrected ? "corrected" : "rejected",
      "regions" => 1,
      "targets" => 1,
      "accepted" => corrected ? 1 : 0,
      "accepted_regions" => corrected ? 1 : 0,
      "rejected" => corrected ? 0 : 1,
      "failed" => 0
    }
    record = {
      "target_id" => "#/texts/1",
      "kind" => "replacement",
      "region_ids" => [ "#/texts/1" ],
      "region_id" => "#/texts/1",
      "page" => 1,
      "status" => correction_status
    }
    mathml = '<math data-correction-id="#/texts/1" xmlns="http://www.w3.org/1998/Math/MathML"><mi>x</mi></math>'
    derived_html = "<div class='page' id='page-1'>#{mathml}</div>"
    if corrected
      record.merge!(
        "docling_ref" => "#/texts/1",
        "charspan" => [ 0, 1 ],
        "before" => "x",
        "after" => "$x$",
        "mathml" => mathml,
        "proposal" => "x",
        "source_tokens" => [ "x" ],
        "proposal_tokens" => [ "x" ],
        "source_signature" => [ "x" ],
        "proposal_signature" => [ "x" ],
        "source_proofs" => [
          { "region_id" => "#/texts/1", "tokens" => [ "x" ], "signature" => [ "x" ] }
        ],
        "proposals" => [
          {
            "selected_engine" => "deterministic_source",
            "proposal_tokens" => [ "x" ],
            "proposal_signature" => [ "x" ]
          }
        ]
      )
    else
      record["reason"] = "proposal_not_proven_by_source"
    end
    corrections = JSON.generate("summary" => counts, "records" => [ record ])
    derived_document = JSON.generate(
      "schema_name" => "DoclingDocument",
      "texts" => [ { "text" => "autre" }, { "text" => "$x$" } ],
      "pages" => { "1" => {} }
    )
    native_page_html = "<div class='page' id='page-1'>native</div>"
    report = {
      "contract" => {
        "version" => MathQualification::CONTRACT_VERSION,
        "analyzer_version" => MathQualification::ANALYZER_VERSION,
        "capability_profile" => MathQualification::CAPABILITY_PROFILE,
        "source_sha256" => qualification.source_sha256,
        "docling_document_sha256" => qualification.docling_document_sha256
      },
      "coverage" => {
        "pages_total" => 1,
        "pages_traced" => 1,
        "pages_traced_with_exclusions" => 0,
        "pages_partially_traced" => 0,
        "pages_unsupported" => 0,
        "pages_ambiguous" => 0
      },
      "pages" => [ { "page" => 1, "status" => "traced" } ],
      "alignment" => {
        "pdf_source_math_regions" => [
          region("#/texts/0", "conformant_within_scope"),
          region("#/texts/1", "contradicted")
        ],
        "evaluation" => {
          "overall" => {
            "regions" => 2,
            "verdicts" => {
              "conformant_within_scope" => 1,
              "contradicted" => 1,
              "non_verifiable" => 0
            }
          }
        }
      },
      "correction" => {
        "status" => corrected ? "corrected" : "rejected",
        "regions" => 1,
        "targets" => 1,
        "accepted" => corrected ? 1 : 0,
        "accepted_regions" => corrected ? 1 : 0,
        "rejected" => corrected ? 0 : 1,
        "failed" => 0,
        "engine" => { "model" => "gemma" },
        "artifacts" => {
          "corrections" => artifact_metadata(corrections),
          "correction_evidence" => artifact_metadata("PK")
        }.tap do |artifacts|
          if corrected
            artifacts["derived_docling_document"] = artifact_metadata(derived_document)
            artifacts["derived_html"] = artifact_metadata(derived_html)
            artifacts["derived_markdown"] = artifact_metadata("$x$")
          end
        end
      },
      "native_page_html" => artifact_metadata(native_page_html)
    }
    report_bytes = JSON.generate(report)
    MathQualificationClient::Result.new(
      raw_response: "flux complet\n",
      report: report,
      report_bytes: report_bytes,
      evidence: "preuve gzip",
      corrections: corrections,
      correction_evidence: "PK",
      derived_docling_document: corrected ? derived_document : "",
      derived_html: corrected ? derived_html : "",
      derived_markdown: corrected ? "$x$".dup : "",
      native_page_html: native_page_html
    )
  end

  def artifact_metadata(content)
    { "bytes" => content.bytesize, "sha256" => Digest::SHA256.hexdigest(content) }
  end

  def region(id, verdict)
    {
      "region_id" => id,
      "page" => 1,
      "bbox" => [ 0, 0, 10, 10 ],
      "source_glyph_text" => "x",
      "source_canonical_tokens" => [ "x" ],
      "docling_ref" => id,
      "candidate_charspan" => [ 0, 1 ],
      "candidate_text" => "x",
      "candidate_link_status" => "linked",
      "candidate_alignment_method" => "normalized_bbox_and_global_text_glyph_alignment",
      "candidate_link_reason" => nil,
      "verdict" => verdict,
      "semantic_reasons" => []
    }
  end

  class FakeClient
    def initialize(result = nil, error: nil)
      @result = result
      @error = error
    end

    def qualify(**_arguments)
      yield({ "phase" => "source_analysis", "completed_units" => 0, "total_units" => 1 })
      raise @error if @error

      yield({ "phase" => "candidate_evaluation", "completed_units" => 1, "total_units" => 1 })
      @result
    end
  end
end
