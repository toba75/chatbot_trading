require "test_helper"

class ConversionAttemptTest < ActiveSupport::TestCase
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"
  OPTIONS = { "pipeline" => "vlm", "document_timeout" => 86_400 }.freeze

  test "publie chaque changement persistant sur les flux du document et de l'index" do
    attempt = create_attempt

    assert_difference -> { SolidQueue::Job.count }, 2 do
      attempt.update!(status: "converting", started_at: Time.current, execution_job_id: "job-1")
    end
    assert_equal [ "default", "default" ], SolidQueue::Job.order(:id).last(2).map(&:queue_name)
  end

  test "refuse un état de conversion sans propriétaire d'exécution" do
    attempt = create_attempt
    attempt.status = "converting"

    assert_not_predicate attempt, :valid?
    assert_includes attempt.errors.details[:execution_job_id], { error: :blank }
  end

  test "dérive du JSON canonique les pages vides et les images" do
    attempt = create_attempt
    attach_json(attempt, docling_document)

    assert_equal [
      { number: 1, blank: false },
      { number: 2, blank: false },
      { number: 3, blank: false },
      { number: 4, blank: false },
      { number: 5, blank: true }
    ], attempt.page_inventory
    assert_equal 2, attempt.picture_count
    assert_equal [ 2, 3 ], attempt.picture_pages
  end

  test "compte une image une seule fois lorsqu'elle possède plusieurs provenances" do
    data = docling_document
    data["pictures"] = [ { "prov" => [ { "page_no" => 2 }, { "page_no" => 3 } ] } ]
    attempt = create_attempt
    attach_json(attempt, data)

    assert_equal 1, attempt.picture_count
    assert_equal [ 2, 3 ], attempt.picture_pages
  end

  test "conserve l'historique des documents créés par les anciennes relances" do
    original = Document.create_from_pdf!(uploaded_file)
    original_attempt = original.start_conversion!(conversion_options: OPTIONS)
    retried = Document.create_from_pdf!(uploaded_file)
    retried.update!(retried_from: original)
    current_attempt = retried.start_conversion!(conversion_options: OPTIONS)

    assert_equal [ current_attempt, original_attempt ], retried.attempt_history.to_a
  end

  test "relance une qualification échouée sans remplacer ses preuves" do
    attempt = create_attempt
    attempt.update!(status: "succeeded")
    failed = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
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
      error_message: "Analyse interrompue.",
      completed_at: Time.current
    )

    retry_qualification = attempt.retry_math_qualification! { |_qualification| }

    assert_equal [ failed, retry_qualification ], attempt.reload.math_qualifications.to_a
    assert_equal retry_qualification, attempt.current_math_qualification
    assert_predicate retry_qualification, :queued?
    assert_equal failed.source_sha256, retry_qualification.source_sha256
    assert_equal failed.docling_document_sha256, retry_qualification.docling_document_sha256
    assert_equal "preuve de l’échec".b, failed.analyzer_response.download
  end

  test "refuse de relancer une qualification qui n'a pas échoué" do
    attempt = create_attempt
    attempt.update!(status: "succeeded")
    MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    ).save!

    assert_raises(ConversionAttempt::MathQualificationNotRetryable) do
      attempt.retry_math_qualification! { |_qualification| }
    end
    assert_equal 1, attempt.math_qualifications.count
  end

  test "autorise de rejouer une qualification courante en développement" do
    attempt = create_attempt
    attempt.update!(status: "succeeded")
    previous = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    )
    previous.save!
    previous.update!(status: "succeeded", completed_at: Time.current)

    current = with_current_math_requalification do
      attempt.retry_math_qualification! { |_qualification| }
    end

    assert_equal [ previous, current ], attempt.reload.math_qualifications.to_a
    assert_predicate current, :queued?
    assert_not current.derived_docling_document.attached?
    assert_not current.derived_html.attached?
    assert_not current.derived_markdown.attached?
    assert_not current.native_page_html.attached?
  end

  test "refuse même en développement de relancer une qualification obsolète non terminée" do
    attempt = create_attempt
    attempt.update!(status: "succeeded")
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.save!
    qualification.update_columns(analyzer_version: "0.5.1")

    with_current_math_requalification do
      assert_raises(ConversionAttempt::MathQualificationNotRetryable) do
        attempt.retry_math_qualification! { |_qualification| }
      end
    end

    assert_equal 1, attempt.math_qualifications.count
  end

  test "relance une qualification produite par un analyseur obsolète" do
    attempt = create_attempt
    attempt.update!(status: "succeeded")
    previous = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    )
    previous.save!
    previous.update_columns(status: "succeeded", analyzer_version: "0.5.1")

    current = attempt.retry_math_qualification! { |_qualification| }

    assert_equal [ previous, current ], attempt.reload.math_qualifications.to_a
    assert_equal MathQualification::ANALYZER_VERSION, current.analyzer_version
    assert_predicate current, :current_contract?
  end

  private

  def create_attempt
    document = Document.create_from_pdf!(uploaded_file)
    document.start_conversion!(conversion_options: OPTIONS)
  end

  def uploaded_file
    tempfile = Tempfile.new([ "reference", ".pdf" ])
    File.open(REFERENCE_PDF, "rb") { |source| IO.copy_stream(source, tempfile) }
    tempfile.rewind
    ActionDispatch::Http::UploadedFile.new(
      tempfile: tempfile,
      filename: File.basename(REFERENCE_PDF),
      type: "application/pdf"
    )
  end

  def attach_json(attempt, content)
    attempt.docling_document.attach(
      io: StringIO.new(JSON.generate(content)),
      filename: "document.json",
      content_type: "application/json"
    )
  end

  def docling_document
    {
      "pages" => (1..5).to_h { |page| [ page.to_s, { "page_no" => page } ] },
      "texts" => (1..4).map { |page| { "prov" => [ { "page_no" => page } ] } },
      "tables" => [],
      "pictures" => [
        { "prov" => [ { "page_no" => 2 } ] },
        { "prov" => [ { "page_no" => 3 } ] }
      ]
    }
  end
end
