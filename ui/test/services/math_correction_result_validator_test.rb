require "test_helper"
require "digest"
require "json"

class MathCorrectionResultValidatorTest < ActiveSupport::TestCase
  Result = Data.define(
    :corrections,
    :correction_evidence,
    :derived_docling_document,
    :derived_html,
    :derived_markdown
  )

  test "refuse une formule acquise sans ancrage de rendu prouvé" do
    native = {
      "schema_name" => "DoclingDocument",
      "texts" => [],
      "body" => { "children" => [] },
      "pages" => { "1" => {} }
    }
    bbox = [ 10.0, 20.0, 30.0, 40.0 ]
    derived = Marshal.load(Marshal.dump(native))
    derived["texts"] << {
      "self_ref" => "#/texts/0",
      "parent" => { "cref" => "#/body" },
      "label" => "formula",
      "orig" => "x",
      "text" => "x",
      "prov" => [
        {
          "page_no" => 1,
          "bbox" => {
            "l" => bbox[0], "t" => bbox[1], "r" => bbox[2], "b" => bbox[3]
          }
        }
      ]
    }
    derived["body"]["children"] << { "cref" => "#/texts/0" }
    mathml = '<math data-correction-id="missing:1"><mi>x</mi></math>'
    record = {
      "target_id" => "missing:1",
      "kind" => "formula_insertion",
      "region_ids" => [ "missing:1" ],
      "region_id" => "missing:1",
      "page" => 1,
      "docling_ref" => nil,
      "charspan" => nil,
      "before" => "",
      "after" => "x",
      "mathml" => mathml,
      "derived_docling_ref" => "#/texts/0",
      "insertion_bbox" => bbox,
      "source_proofs" => [
        { "region_id" => "missing:1", "tokens" => [ "x" ], "signature" => [ "x" ] }
      ],
      "proposals" => [
        {
          "selected_engine" => "deterministic_source_confirmed_by_vision",
          "proposal_tokens" => [ "x" ],
          "proposal_signature" => [ "x" ],
          "vision_proposal" => "x",
          "vision_confirmation" => "exact",
          "crop_sha256" => "a" * 64
        }
      ],
      "status" => "accepted"
    }
    summary = {
      "status" => "corrected",
      "regions" => 1,
      "target_region_ids" => [ "missing:1" ],
      "targets" => 1,
      "accepted" => 1,
      "accepted_regions" => 1,
      "rejected" => 0,
      "failed" => 0
    }
    corrections = JSON.generate("summary" => summary, "records" => [ record ])
    derived_document = JSON.generate(derived)
    derived_html = "<div class='page' id='page-1'>#{mathml}</div>"
    result = Result.new(
      corrections: corrections,
      correction_evidence: "PK",
      derived_docling_document: derived_document,
      derived_html: derived_html,
      derived_markdown: "x"
    )
    correction = summary.merge(
      "engine" => { "model" => "gemma" },
      "artifacts" => {
        "corrections" => metadata(corrections),
        "correction_evidence" => metadata("PK"),
        "derived_docling_document" => metadata(derived_document),
        "derived_html" => metadata(derived_html),
        "derived_markdown" => metadata("x")
      }
    )

    assert_raises(MathCorrectionResultValidator::InvalidResult) do
      MathCorrectionResultValidator.new(
        result,
        native_document: JSON.generate(native)
      ).validate(correction, available_region_ids: [ "missing:1" ])
    end
  end

  test "refuse une commande LaTeX brute dans le rendu visible" do
    native = {
      "schema_name" => "DoclingDocument",
      "texts" => [ { "text" => "x" } ],
      "pages" => { "1" => {} }
    }
    derived = Marshal.load(Marshal.dump(native))
    derived["texts"][0]["text"] = "$x$"
    mathml = '<math data-correction-id="source:1"><mi>x</mi></math>'
    record = {
      "target_id" => "source:1",
      "kind" => "replacement",
      "region_ids" => [ "source:1" ],
      "region_id" => "source:1",
      "page" => 1,
      "docling_ref" => "#/texts/0",
      "charspan" => [ 0, 1 ],
      "derived_docling_ref" => "#/texts/0",
      "derived_charspan" => [ 0, 3 ],
      "before" => "x",
      "after" => "$x$",
      "mathml" => mathml,
      "source_proofs" => [
        { "region_id" => "source:1", "tokens" => [ "x" ], "signature" => [ "x" ] }
      ],
      "proposals" => [
        {
          "selected_engine" => "deterministic_source",
          "proposal_tokens" => [ "x" ],
          "proposal_signature" => [ "x" ]
        }
      ],
      "status" => "accepted"
    }
    summary = {
      "status" => "corrected",
      "regions" => 1,
      "target_region_ids" => [ "source:1" ],
      "targets" => 1,
      "accepted" => 1,
      "accepted_regions" => 1,
      "rejected" => 0,
      "failed" => 0
    }
    corrections = JSON.generate("summary" => summary, "records" => [ record ])
    derived_document = JSON.generate(derived)
    derived_html = "<div class='page' id='page-1'>#{mathml}<math><mi>\\arg</mi></math></div>"
    result = Result.new(
      corrections: corrections,
      correction_evidence: "PK",
      derived_docling_document: derived_document,
      derived_html: derived_html,
      derived_markdown: "$x$"
    )
    correction = summary.merge(
      "engine" => { "model" => "gemma" },
      "artifacts" => {
        "corrections" => metadata(corrections),
        "correction_evidence" => metadata("PK"),
        "derived_docling_document" => metadata(derived_document),
        "derived_html" => metadata(derived_html),
        "derived_markdown" => metadata("$x$")
      }
    )

    assert_raises(MathCorrectionResultValidator::InvalidResult) do
      MathCorrectionResultValidator.new(
        result,
        native_document: JSON.generate(native)
      ).validate(correction, available_region_ids: [ "source:1" ])
    end
  end

  test "exige une preuve visuelle pour une formule complÃ¨te" do
    validator = MathCorrectionResultValidator.new(
      Object.new,
      native_document: "{}"
    )
    record = {
      "kind" => "formula_replacement",
      "region_ids" => [ "formula:1" ],
      "source_proofs" => [
        {
          "region_id" => "formula:1",
          "candidate_charspan" => [ 0, 1 ],
          "candidate_text" => "z",
          "tokens" => [ "x" ],
          "signature" => [ "x" ]
        }
      ],
      "proposals" => [
        {
          "selected_engine" => "deterministic_source",
          "proposal_tokens" => [ "x" ],
          "proposal_signature" => [ "x" ]
        }
      ]
    }

    assert_not validator.send(:valid_proposals?, record)

    record["proposals"][0].merge!(
      "selected_engine" => "vision_proven_by_source",
      "vision_proposal" => "x",
      "vision_proposal_tokens" => [ "x" ],
      "vision_proposal_signature" => [ "x" ],
      "vision_confirmation" => "exact",
      "crop_sha256" => "a" * 64
    )
    assert validator.send(:valid_proposals?, record)

    record["proposals"][0]["selected_engine"] = "deterministic_source"
    assert_not validator.send(:valid_proposals?, record)
    record["proposals"][0]["selected_engine"] = "vision_proven_by_source"

    record.merge!(
      "page" => 1,
      "after" => "x",
      "before" => "z",
      "mathml" => '<math data-correction-id="formula:1"><mi>x</mi></math>',
      "docling_ref" => "#/texts/0",
      "charspan" => [ 0, 1 ],
      "derived_docling_ref" => "#/texts/0",
      "derived_charspan" => [ 0, 1 ]
    )
    assert validator.send(:valid_accepted_record?, record)

    record["after"] = "y"
    record["mathml"] = '<math data-correction-id="formula:1"><mi>y</mi></math>'
    assert_not validator.send(:valid_accepted_record?, record)

    record["proposals"][0]["vision_proposal"] = nil
    assert_not validator.send(:valid_proposals?, record)
  end

  test "ignore le LaTeX brut d une annotation MathML namespacÃ©e" do
    correction_math = '<math data-correction-id="source:1"><mi>x</mi></math>'
    annotation_math = <<~HTML
      <math xmlns="http://www.w3.org/1998/Math/MathML">
        <semantics><mi>y</mi><annotation encoding="TeX">\\arg y</annotation></semantics>
      </math>
    HTML
    html = <<~HTML
      <div class="page" id="page-1">#{correction_math}#{annotation_math}</div>
    HTML
    result = Struct.new(:derived_html).new(html)
    validator = MathCorrectionResultValidator.new(result, native_document: "{}")
    native = { "pages" => { "1" => {} } }
    accepted = [
      { "target_id" => "source:1", "page" => 1, "mathml" => correction_math }
    ]

    assert_nothing_raised do
      validator.send(:validate_html_pages!, native, accepted)
    end
  end

  test "valide un document développé contenant un supplément PDF" do
    native = {
      "schema_name" => "DoclingDocument",
      "pages" => { "1" => {} },
      "body" => { "children" => [] },
      "texts" => []
    }
    bbox = [ 10.0, 20.0, 30.0, 40.0 ]
    reference = "#/texts/0"
    supplement = {
      "operation" => "pdf_supplement",
      "kind" => "pdf_supplement",
      "origin" => "pdf_supplement",
      "status" => "accepted",
      "target_id" => "supplement:1",
      "region_id" => "supplement:1",
      "page" => 1,
      "bbox" => bbox,
      "before" => "",
      "after" => "x",
      "source_text" => "x",
      "source_tokens" => [ "x" ],
      "source_signature" => [ "x" ],
      "source_proof" => {
        "region_id" => "supplement:1",
        "candidate_link_reason" => { "code" => "docling_text_container_missing" },
        "verdict" => "non_verifiable"
      },
      "derived_docling_ref" => reference,
      "derived_charspan" => [ 0, 1 ]
    }
    derived = Marshal.load(Marshal.dump(native))
    derived["texts"] << {
      "self_ref" => reference,
      "parent" => { "cref" => "#/body" },
      "children" => [],
      "content_layer" => "body",
      "meta" => { "rag__development_origin" => "pdf_supplement" },
      "label" => "formula",
      "prov" => [
        {
          "page_no" => 1,
          "bbox" => {
            "l" => bbox[0], "t" => bbox[1], "r" => bbox[2], "b" => bbox[3],
            "coord_origin" => "TOPLEFT"
          },
          "charspan" => [ 0, 1 ]
        }
      ],
      "orig" => "x",
      "text" => "x"
    }
    derived["body"]["children"] << { "cref" => reference }
    derived_document = JSON.generate(derived)
    native_document = JSON.generate(native)
    recipe = {
      "schema_version" => 1,
      "operations" => [ supplement ]
    }
    recipe_sha256_value = MathCorrectionResultValidator.new(
      Result.new(nil, nil, nil, nil, nil),
      native_document: native_document
    ).send(:recipe_sha256, recipe)
    native_sha256 = Digest::SHA256.hexdigest(native_document)
    derived_html = <<~HTML
      <html><head><meta name="development-native-document-sha256" content="#{native_sha256}"><meta name="development-recipe-sha256" content="#{recipe_sha256_value}"></head><body>
      <div class="page" id="page-1">
        <span class="pdf-supplement" data-origin="pdf_supplement" data-supplement-id="supplement:1">
          <span class="pdf-supplement-label">Supplément PDF dérivé</span>
          <math data-origin="pdf_supplement" data-docling-ref="#/texts/0" data-docling-charspan="0:1"><mi>x</mi></math>
        </span>
      </div>
      </body></html>
    HTML
    markdown = "<!-- native_document_sha256: #{native_sha256} -->\n" \
      "<!-- recipe_sha256: #{recipe_sha256_value} -->\n" \
      "> **Supplément PDF dérivé** — région supplement:1, page 1.\n>\n> $$x$$"
    payload_summary = {
      "status" => "corrected",
      "regions" => 0,
      "target_region_ids" => [],
      "targets" => 0,
      "accepted" => 0,
      "accepted_regions" => 0,
      "rejected" => 0,
      "failed" => 0,
      "supplements" => 1,
      "development_operations" => 1,
      "recipe_schema_version" => 1,
      "recipe_sha256" => recipe_sha256_value,
      "native_document_sha256" => native_sha256
    }
    corrections = JSON.generate(
      "summary" => payload_summary,
      "records" => [],
      "supplements" => [ supplement ],
      "recipe" => recipe
    )
    result = Result.new(
      corrections: corrections,
      correction_evidence: "PK",
      derived_docling_document: derived_document,
      derived_html: derived_html,
      derived_markdown: markdown
    )
    correction = payload_summary.merge(
      "engine" => { "model" => "gemma" },
      "artifacts" => {
        "corrections" => metadata(corrections),
        "correction_evidence" => metadata("PK"),
        "derived_docling_document" => metadata(derived_document),
        "derived_html" => metadata(derived_html),
        "derived_markdown" => metadata(markdown)
      }
    )

    validated = MathCorrectionResultValidator.new(
      result,
      native_document: native_document
    ).validate(correction, available_region_ids: [])

    assert_equal 1, validated.fetch("supplements")
    assert_equal 1, validated.fetch("development_operations")
    assert_equal "corrected", validated.fetch("status")
  end

  private

  def metadata(content)
    { "bytes" => content.bytesize, "sha256" => Digest::SHA256.hexdigest(content) }
  end
end
