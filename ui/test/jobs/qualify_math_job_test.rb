require "test_helper"
require "securerandom"

class QualifyMathJobTest < ActiveJob::TestCase
  test "refuse de qualifier un document supprimé" do
    qualification = create_qualification
    qualification.conversion_attempt.document.discard!

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new).perform(qualification)
    end

    assert_predicate MathQualification.unscoped.find(qualification.id), :staging?
  end

  test "n'enregistre aucune preuve si le document est supprimé pendant la qualification" do
    qualification = create_qualification
    client = DiscardingClient.new(qualification, successful_result)

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(client).perform(qualification)
    end

    stored_qualification = MathQualification.unscoped.find(qualification.id)
    assert_predicate stored_qualification, :running?
    assert_not stored_qualification.analyzer_response.attached?
    assert_not stored_qualification.report.attached?
  end

  test "purge les preuves si le document est supprimé pendant leur stockage" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    original_attach = job.method(:attach)
    first_attachment = true
    job.define_singleton_method(:attach) do |attachment, content, filename, content_type|
      original_attach.call(attachment, content, filename, content_type)
      if first_attachment
        first_attachment = false
        Document.with_discarded.find(qualification.conversion_attempt.document_id).discard!
      end
    end

    assert_raises(QualifyMathJob::InvalidState) { job.perform(qualification) }

    stored_qualification = MathQualification.unscoped.find(qualification.id)
    assert_not stored_qualification.analyzer_response.attached?
    assert_not stored_qualification.report.attached?
  end

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
    assert_equal(
      '{"schema_name":"DoclingDocument","texts":[' \
      '{"self_ref":"#/texts/0","label":"text","text":"x"},' \
      '{"self_ref":"#/texts/1","label":"text","text":"x"}' \
      '],"pages":{"1":{}}}',
      qualification.conversion_attempt.docling_document.download
    )
  end

  test "accepte une normalisation de rendu sur une région conforme" do
    qualification = create_qualification
    result = successful_result(corrected: true)
    result.report.dig("alignment", "pdf_source_math_regions").last["verdict"] = "conformant_within_scope"
    result.report.dig("alignment", "evaluation", "overall", "verdicts").merge!(
      "conformant_within_scope" => 2,
      "contradicted" => 0
    )
    registry = JSON.parse(result.corrections)
    registry.dig("records", 0)["kind"] = "render_normalization"
    result.corrections.replace(JSON.generate(registry))
    result.report.dig("correction", "artifacts", "corrections").replace(
      artifact_metadata(result.corrections)
    )
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    qualification.reload
    assert_predicate qualification, :succeeded?
    assert_predicate qualification, :conformant_within_scope?
    assert_equal "corrected", qualification.summary.dig("correction", "status")
  end

  test "ne marque pas la qualification réussie lorsque le stockage des preuves échoue" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    job.define_singleton_method(:attach_result) do |_qualification, _result|
      raise IOError, "disque plein"
    end

    assert_raises(IOError) { job.perform(qualification) }

    qualification.reload
    assert_predicate qualification, :failed?
    assert_equal "unexpected_error", qualification.error_code
    assert_equal "disque plein", qualification.error_message
    assert_nil qualification.verdict
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
            "operation_indices" => [ 7 ],
            "glyph_sequence_indices" => [],
            "reason" => {
              "code" => "form_xobject_vector_content_unqualified",
              "message" => "Contenu vectoriel non qualifié"
            }
          },
          {
            "kind" => "image_xobject",
            "resource" => "/X2",
            "bbox" => [ 40.0, 50.0, 60.0, 70.0 ],
            "operation_indices" => [ 9 ],
            "glyph_sequence_indices" => [],
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

  test "publie les exclusions de police localisees d'une page partiellement tracee" do
    qualification = create_qualification
    result = successful_result
    reason = {
      "font_resource" => "/F1@12",
      "code" => "identity_cid_to_gid_required",
      "message" => "CIDToGIDMap non supportee"
    }
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_partially_traced" => 1
    )
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "partially_traced",
        "reasons" => [ reason ],
        "font_exclusions" => [
          {
            "kind" => "font",
            "scope" => "line",
            "resources" => [ "/F1@12" ],
            "trace_font" => "LimitedFont",
            "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
            "operation_index_ranges" => [ [ 7, 7 ] ],
            "glyph_sequence_index_ranges" => [ [ 10, 11 ] ],
            "reasons" => [ reason ]
          }
        ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    exclusion = qualification.reload.summary.fetch("page_exclusions").sole
    assert_equal "partially_traced", exclusion.fetch("status")
    assert_equal "font", exclusion.dig("regions", 0, "kind")
    assert_equal "/F1@12", exclusion.dig("regions", 0, "resource")
    assert_equal [ 10.0, 20.0, 30.0, 40.0 ], exclusion.dig("regions", 0, "bbox")
    assert_equal [ [ 7, 7 ] ], exclusion.dig("regions", 0, "operation_index_ranges")
    assert_equal [ [ 10, 11 ] ], exclusion.dig("regions", 0, "glyph_sequence_index_ranges")
  end

  test "refuse une page partielle sans exclusion de police localisee" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_partially_traced" => 1
    )
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "partially_traced",
        "reasons" => [
          {
            "font_resource" => "/F1@12",
            "code" => "identity_cid_to_gid_required",
            "message" => "CIDToGIDMap non supportee"
          }
        ]
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une page unsupported sans preuve d'exclusion" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_unsupported" => 1
    )
    result.report["pages"] = [
      { "page" => 1, "status" => "unsupported", "reasons" => [] }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "accepte plusieurs exclusions localisees pour la meme police unsupported" do
    qualification = create_qualification
    result = successful_result
    reason = {
      "font_resource" => "/F1",
      "code" => "font_encoding_unsupported",
      "message" => "Police non qualifiee"
    }
    exclusion = {
      "kind" => "font",
      "scope" => "line",
      "resources" => [ "/F1" ],
      "trace_font" => "LimitedFont",
      "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
      "operation_index_ranges" => [ [ 7, 7 ] ],
      "glyph_sequence_index_ranges" => [ [ 10, 11 ] ],
      "reasons" => [ reason ]
    }
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_unsupported" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "unsupported",
        "box" => [ 0.0, 0.0, 100.0, 120.0 ],
        "reasons" => [ reason ],
        "font_exclusions" => [
          exclusion,
          exclusion.merge("bbox" => [ 10.0, 50.0, 30.0, 70.0 ])
        ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    assert_predicate qualification.reload, :succeeded?
    assert_equal 2, qualification.summary.dig("page_exclusions", 0, "regions").size
  end

  test "refuse une raison de police unsupported sans ressource de police" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_unsupported" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "unsupported",
        "box" => [ 0.0, 0.0, 100.0, 120.0 ],
        "reasons" => [
          { "code" => "font_encoding_unsupported", "message" => "Police inconnue" }
        ]
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "accepte une ambiguite de rendu de police au niveau de la page" do
    qualification = create_qualification
    result = successful_result
    reason = {
      "code" => "rendered_font_mismatch",
      "message" => "Police trace divergente a 1102"
    }
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_ambiguous" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "ambiguous",
        "box" => [ 0.0, 0.0, 100.0, 120.0 ],
        "reasons" => [ reason ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    qualification.reload
    assert_predicate qualification, :succeeded?
    exclusion = qualification.summary.fetch("page_exclusions").sole
    assert_equal "rendered_font_mismatch", exclusion.dig("regions", 0, "resource")
    assert_equal reason, exclusion.fetch("reasons").sole
  end

  test "refuse une ambiguite de rendu declaree unsupported" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_unsupported" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "unsupported",
        "box" => [ 0.0, 0.0, 100.0, 120.0 ],
        "reasons" => [
          {
            "code" => "rendered_font_mismatch",
            "message" => "Police trace divergente a 1102"
          }
        ]
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une exclusion de police sans indice probant" do
    qualification = create_qualification
    result = successful_result
    reason = {
      "font_resource" => "/F1",
      "code" => "font_encoding_unsupported",
      "message" => "Police non qualifiee"
    }
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_unsupported" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "unsupported",
        "box" => [ 0.0, 0.0, 100.0, 120.0 ],
        "reasons" => [ reason ],
        "font_exclusions" => [
          {
            "kind" => "font", "scope" => "line", "resources" => [ "/F1" ],
            "trace_font" => "LimitedFont", "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
            "operation_indices" => [], "glyph_sequence_indices" => [],
            "reasons" => [ reason ]
          }
        ]
      }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "conserve ensemble les exclusions de police et de xobject" do
    qualification = create_qualification
    result = successful_result
    font_reason = {
      "font_resource" => "/F1@12",
      "code" => "identity_cid_to_gid_required",
      "message" => "CIDToGIDMap non supportee"
    }
    opaque_reason = {
      "code" => "image_xobject_content_unqualified",
      "message" => "Contenu matriciel non qualifie"
    }
    result.report.fetch("coverage").merge!(
      "pages_traced" => 0,
      "pages_partially_traced" => 1
    )
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "partially_traced",
        "reasons" => [ font_reason ],
        "font_exclusions" => [
          {
            "kind" => "font",
            "scope" => "line",
            "resources" => [ "/F1@12" ],
            "trace_font" => "LimitedFont",
            "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
            "operation_indices" => [ 7 ],
            "glyph_sequence_indices" => [ 10, 11 ],
            "reasons" => [ font_reason ]
          }
        ],
        "opaque_regions" => [
          {
            "kind" => "image_xobject",
            "resource" => "/Im1",
            "bbox" => [ 50.0, 60.0, 70.0, 80.0 ],
            "operation_indices" => [ 9 ],
            "glyph_sequence_indices" => [],
            "reason" => opaque_reason
          }
        ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    exclusion = qualification.reload.summary.fetch("page_exclusions").sole
    assert_equal %w[font image_xobject], exclusion.fetch("regions").pluck("kind")
    assert_equal [ font_reason, opaque_reason ], exclusion.fetch("reasons")
  end

  test "accepte les raisons de police equivalentes dans un ordre different" do
    qualification = create_qualification
    result = successful_result
    reasons = [ "/Z", "/A" ].map do |resource|
      {
        "font_resource" => resource,
        "code" => "identity_cid_to_gid_required",
        "message" => "CIDToGIDMap non supportee"
      }
    end
    result.report.fetch("coverage").merge!("pages_traced" => 0, "pages_partially_traced" => 1)
    result.report["pages"] = [
      {
        "page" => 1,
        "status" => "partially_traced",
        "reasons" => reasons,
        "font_exclusions" => [
          {
            "kind" => "font",
            "scope" => "line",
            "resources" => [ "/A", "/Z" ],
            "trace_font" => "LimitedFont",
            "bbox" => [ 10.0, 20.0, 30.0, 40.0 ],
            "operation_indices" => [ 7 ],
            "glyph_sequence_indices" => [ 10, 11 ],
            "reasons" => reasons.reverse
          }
        ]
      }
    ]
    result = result.with(report_bytes: JSON.generate(result.report))

    job_with(FakeClient.new(result)).perform(qualification)

    assert_predicate qualification.reload, :succeeded?
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

  test "refuse un audit html qui designe le mauvais artefact" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("html_integrity")["artifact"] = "derived_html"

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un audit html qui ne couvre pas toutes les pages" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("html_integrity")["pages_checked"] = 0

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un audit html sans preuve par page" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("html_integrity").delete("pages")

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une page html passee dont les inventaires divergent" do
    qualification = create_qualification
    result = successful_result
    page = result.report.dig("html_integrity", "pages").sole
    page["expected"]["math"] = 1

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse la disparition des liens entre regions prouvees et dom" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("html_integrity")["region_links"] = []

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un lien dom matched sans occurrence" do
    qualification = create_qualification
    result = successful_result
    result.report.dig("html_integrity", "region_links").first["matches"] = 0

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un lien dom qui contredit la region source" do
    qualification = create_qualification
    result = successful_result
    link = result.report.dig("html_integrity", "region_links").first
    link.merge!(
      "page" => 999,
      "docling_ref" => "#/texts/999",
      "candidate_charspan" => [ 100, 200 ],
      "dom_charspan" => [ 100, 200 ],
      "dom_selector" => (
        "math[@data-docling-ref='#/texts/999']" \
        "[@data-docling-charspan='100:200']"
      )
    )

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un charspan dom arbitraire avec un selecteur auto coherent" do
    qualification = create_qualification
    result = successful_result
    link = result.report.dig("html_integrity", "region_links").first
    link["dom_charspan"] = [ 100, 200 ]
    link["dom_selector"] = (
      "math[@data-docling-ref='#/texts/0']" \
      "[@data-docling-charspan='100:200']"
    )

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une anomalie html rattachee a une page inexistante" do
    qualification = create_qualification
    result = successful_result
    integrity = result.report.fetch("html_integrity")
    integrity["status"] = "failed"
    integrity["issues"] = [
      { "page" => 999, "code" => "invalid", "message" => "hors document" }
    ]

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse une page html failed sans anomalie correspondante" do
    qualification = create_qualification
    result = successful_result
    result.report.dig("html_integrity", "pages").sole["status"] = "failed"

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "refuse un total de pages html different de la couverture" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("html_integrity").merge!("pages_total" => 2, "pages_checked" => 2)

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
  end

  test "audite le html derive si une correction est acceptee avant un echec" do
    qualification = create_qualification

    job_with(FakeClient.new(successful_result(corrected: true, mixed: true))).perform(qualification)

    assert_predicate qualification.reload, :succeeded?
    assert_equal "failed", qualification.summary.dig("correction", "status")
    assert_equal "derived_html", qualification.summary.dig("html_integrity", "artifact")
  end

  test "refuse une zone opaque sur une page déclarée entièrement tracée" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("pages").first["opaque_regions"] = [
      {
        "kind" => "image_xobject",
        "resource" => "/Im1",
        "bbox" => [ 1.0, 1.0, 2.0, 2.0 ],
        "operation_indices" => [ 1 ],
        "glyph_sequence_indices" => [],
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
    derived_charspan = [ 0, after.length ]
    registry = JSON.parse(result.corrections)
    mathml = (
      "<math data-docling-ref=\"#/texts/1\" " \
      "data-docling-charspan=\"#{derived_charspan.join(':')}\" " \
      "data-correction-id=\"#/texts/1\" " \
      "xmlns=\"http://www.w3.org/1998/Math/MathML\">" \
      "<mi>x</mi><mo>&lt;</mo><mi>y</mi></math>"
    )
    registry.fetch("records").first.merge!(
      "after" => after,
      "mathml" => mathml,
      "derived_charspan" => derived_charspan,
      "proposal" => %q(x'<y\_z > 0),
      "source_tokens" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "proposal_tokens" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "source_signature" => [ "x", "'", "<", "y", "_", "z", ">", "0" ],
      "proposal_signature" => [ "x", "'", "<", "y", "_", "z", ">", "0" ]
    )
    result.corrections.replace(JSON.generate(registry))
    result.derived_docling_document.replace(
      JSON.generate(
        "schema_name" => "DoclingDocument",
        "texts" => [
          { "self_ref" => "#/texts/0", "label" => "text", "text" => "x" },
          { "self_ref" => "#/texts/1", "label" => "text", "text" => after }
        ],
        "pages" => { "1" => {} }
      )
    )
    result.derived_html.replace("<div class='page' id='page-1'>#{mathml}</div>")
    result.derived_markdown.replace(%q($x'&lt;y\_z &gt; 0$))
    link = result.report.dig("html_integrity", "region_links").last
    link["dom_charspan"] = derived_charspan
    link["dom_selector"] = (
      "math[@data-docling-ref='#/texts/1']" \
      "[@data-docling-charspan='#{derived_charspan.join(':')}']"
    )
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

  test "ne prend pas une qualification déjà mise en file par un autre job" do
    qualification = create_qualification
    qualification.update!(status: "queued", execution_job_id: "job-en-file")

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new(successful_result)).perform(qualification)
    end

    assert_predicate qualification.reload, :queued?
    assert_equal "job-en-file", qualification.execution_job_id
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
    source_sha256 = SecureRandom.hex(32)
    document = Document.create!(source_sha256: source_sha256)
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
      io: StringIO.new(
        '{"schema_name":"DoclingDocument","texts":[' \
        '{"self_ref":"#/texts/0","label":"text","text":"x"},' \
        '{"self_ref":"#/texts/1","label":"text","text":"x"}' \
        '],"pages":{"1":{}}}'
      ),
      filename: "document.json",
      content_type: "application/json"
    )
    MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    ).tap(&:save!)
  end

  def successful_result(corrected: false, mixed: false)
    qualification = MathQualification.last
    correction_status = corrected ? "accepted" : "rejected"
    target_region_ids = mixed ? [ "#/texts/1", "#/texts/0" ] : [ "#/texts/1" ]
    counts = {
      "status" => mixed ? "failed" : (corrected ? "corrected" : "rejected"),
      "regions" => target_region_ids.size,
      "target_region_ids" => target_region_ids,
      "targets" => target_region_ids.size,
      "accepted" => corrected ? 1 : 0,
      "accepted_regions" => corrected ? 1 : 0,
      "rejected" => corrected ? 0 : 1,
      "failed" => mixed ? 1 : 0
    }
    record = {
      "target_id" => "#/texts/1",
      "kind" => "replacement",
      "region_ids" => [ "#/texts/1" ],
      "region_id" => "#/texts/1",
      "page" => 1,
      "status" => correction_status
    }
    mathml = (
      '<math data-docling-ref="#/texts/1" data-docling-charspan="0:3" ' \
      'data-correction-id="#/texts/1" xmlns="http://www.w3.org/1998/Math/MathML">' \
      '<mi>x</mi></math>'
    )
    derived_html = "<div class='page' id='page-1'>#{mathml}</div>"
    if corrected
      record.merge!(
        "docling_ref" => "#/texts/1",
        "charspan" => [ 0, 1 ],
        "derived_docling_ref" => "#/texts/1",
        "derived_charspan" => [ 0, 3 ],
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
    records = [ record ]
    if mixed
      records << {
        "target_id" => "#/texts/0",
        "region_ids" => [ "#/texts/0" ],
        "region_id" => "#/texts/0",
        "status" => "failed",
        "reason" => "proposal_request_failed"
      }
    end
    corrections = JSON.generate("summary" => counts, "records" => records)
    derived_document = JSON.generate(
      "schema_name" => "DoclingDocument",
      "texts" => [
        { "self_ref" => "#/texts/0", "label" => "text", "text" => "x" },
        { "self_ref" => "#/texts/1", "label" => "text", "text" => "$x$" }
      ],
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
      "correction" => counts.merge(
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
      ),
      "native_page_html" => artifact_metadata(native_page_html),
      "html_integrity" => {
        "artifact" => corrected ? "derived_html" : "native_page_html",
        "status" => "passed",
        "pages_total" => 1,
        "pages_checked" => 1,
        "issues" => [],
        "region_links" => [
          {
            "region_id" => "#/texts/0", "page" => 1,
            "docling_ref" => "#/texts/0", "candidate_charspan" => [ 0, 1 ],
            "dom_charspan" => [ 0, 1 ],
            "dom_selector" => (
              "math[@data-docling-ref='#/texts/0']" \
              "[@data-docling-charspan='0:1']"
            ),
            "matches" => 1, "status" => "matched"
          },
          {
            "region_id" => "#/texts/1", "page" => 1,
            "docling_ref" => "#/texts/1", "candidate_charspan" => [ 0, 1 ],
            "dom_charspan" => corrected ? [ 0, 3 ] : [ 0, 1 ],
            "dom_selector" => (
              "math[@data-docling-ref='#/texts/1']" \
              "[@data-docling-charspan='#{corrected ? '0:3' : '0:1'}']"
            ),
            "matches" => 1, "status" => "matched"
          }
        ],
        "pages" => [
          {
            "page" => 1,
            "expected" => { "math" => 0, "images" => 0 },
            "rendered" => { "math" => 0, "images" => 0 },
            "status" => "passed"
          }
        ]
      }
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

  class DiscardingClient < FakeClient
    def initialize(qualification, result)
      super(result)
      @qualification = qualification
    end

    def qualify(**_arguments)
      Document.with_discarded.find(@qualification.conversion_attempt.document_id).discard!
      super
    end
  end
end
