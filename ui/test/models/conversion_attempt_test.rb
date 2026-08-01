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
