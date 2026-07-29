require "test_helper"

class ConvertDocumentJobTest < ActiveJob::TestCase
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"

  test "persiste sans perte toutes les représentations d'une conversion réussie" do
    attempt = create_attempt
    client = FakeClient.new(successful_result)

    job_with(client).perform(attempt)

    attempt.reload
    assert_predicate attempt, :succeeded?
    assert_equal 5, attempt.page_count
    assert_equal 2.5, attempt.processing_seconds
    assert_equal successful_result.raw_body.b, attempt.docling_response.download
    assert_equal successful_result.payload.dig("document", "json_content"), JSON.parse(attempt.docling_document.download)
    assert_equal "<doctag>", attempt.doctags.download
    assert_equal "<html>conversion</html>", attempt.html.download
    assert_equal "# Conversion", attempt.markdown.download
    assert_equal attempt.conversion_options, client.recorded_options
    assert attempt.started_at
    assert attempt.completed_at
  end

  test "rend l'échec Docling visible et laisse le job échouer" do
    attempt = create_attempt
    client = FakeClient.new(error: DoclingClient::ConversionError.new("http_error", "Docling indisponible."))

    error = assert_raises(DoclingClient::ConversionError) do
      job_with(client).perform(attempt)
    end

    assert_equal "http_error", error.code
    attempt.reload
    assert_predicate attempt, :failed?
    assert_equal "http_error", attempt.error_code
    assert_equal "Docling indisponible.", attempt.error_message
    assert attempt.completed_at
  end

  test "conserve la réponse brute et chaque sortie disponible lors d'un échec" do
    attempt = create_attempt
    payload = {
      "status" => "failure",
      "errors" => [ "timeout" ],
      "document" => {
        "json_content" => { "pages" => { "1" => { "page_no" => 1 } } },
        "md_content" => "# Résultat partiel"
      }
    }
    result = DoclingClient::Result.new(payload: payload, raw_body: JSON.generate(payload))
    error = DoclingClient::ConversionError.new("conversion_failed", "Délai dépassé.", result: result)

    assert_raises(DoclingClient::ConversionError) do
      job_with(FakeClient.new(error: error)).perform(attempt)
    end

    attempt.reload
    assert_equal result.raw_body.b, attempt.docling_response.download
    assert_equal payload.dig("document", "json_content"), JSON.parse(attempt.docling_document.download)
    assert_equal "# Résultat partiel".b, attempt.markdown.download
    assert_not attempt.doctags.attached?
    assert_not attempt.html.attached?
  end

  test "termine l'échec lorsque la racine JSON Docling n'est pas un objet" do
    attempt = create_attempt
    result = DoclingClient::Result.new(payload: [], raw_body: "[]")
    error = DoclingClient::ConversionError.new(
      "incomplete_response",
      "La réponse Docling est incomplète.",
      result: result
    )

    assert_raises(DoclingClient::ConversionError) do
      job_with(FakeClient.new(error: error)).perform(attempt)
    end

    attempt.reload
    assert_predicate attempt, :failed?
    assert_equal "incomplete_response", attempt.error_code
    assert_equal "[]".b, attempt.docling_response.download
    assert_not attempt.docling_document.attached?
  end

  private

  def job_with(client)
    ConvertDocumentJob.new.tap do |job|
      job.define_singleton_method(:docling_client) { client }
    end
  end

  def create_attempt
    document = Document.create_from_pdf!(uploaded_file)
    document.start_conversion!(conversion_options: DoclingClient.conversion_options)
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

  def successful_result
    payload = {
      "status" => "success",
      "errors" => [],
      "processing_time" => 2.5,
      "document" => {
        "json_content" => { "pages" => (1..5).to_h { |page| [ page.to_s, { "page_no" => page } ] } },
        "doctags_content" => "<doctag>",
        "html_content" => "<html>conversion</html>",
        "md_content" => "# Conversion"
      }
    }
    DoclingClient::Result.new(payload: payload, raw_body: JSON.generate(payload))
  end

  class FakeClient
    attr_reader :recorded_options

    def initialize(result = nil, error: nil)
      @result = result
      @error = error
    end

    def convert(file:, filename:, options:)
      @recorded_options = options
      raise @error if @error

      @result
    end
  end
end
