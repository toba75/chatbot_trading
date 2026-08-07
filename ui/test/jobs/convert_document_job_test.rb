require "test_helper"

class ConvertDocumentJobTest < ActiveJob::TestCase
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"
  TEST_SERVER = DoclingServerPool::Server.new(
    name: "remote",
    url: "http://docling-remote.test:5001",
    priority: 1
  )

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
    assert_equal "remote", attempt.docling_server_name
    assert_equal TEST_SERVER.url, attempt.docling_server_url
    assert attempt.docling_server_assigned_at
    assert attempt.docling_server_returned_at
    qualification = attempt.current_math_qualification
    assert_predicate qualification, :queued?
    assert_equal attempt.document.source_sha256, qualification.source_sha256
    assert_equal Digest::SHA256.hexdigest(attempt.docling_document.download), qualification.docling_document_sha256
    assert_equal 1, SolidQueue::Job.where(class_name: "QualifyMathJob").count
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
    assert_nil attempt.docling_server_returned_at
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
    assert attempt.docling_server_returned_at
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

  test "conserve le succès Docling et rend un échec d'enqueue visible" do
    attempt = create_attempt
    job = job_with(FakeClient.new(successful_result))
    job.define_singleton_method(:enqueue_math_qualification) do |_qualification|
      raise SolidQueue::Job::EnqueueError, "base indisponible"
    end

    job.perform(attempt)

    attempt.reload
    assert_predicate attempt, :succeeded?
    assert_predicate attempt.current_math_qualification, :failed?
    assert_equal "enqueue_failed", attempt.current_math_qualification.error_code
    assert_equal 0, SolidQueue::Job.where(class_name: "QualifyMathJob").count
  end

  test "ne marque pas la conversion réussie lorsque le stockage des sorties échoue" do
    attempt = create_attempt
    job = job_with(FakeClient.new(successful_result))
    job.define_singleton_method(:persist_outputs!) do |_attempt, _result|
      raise IOError, "disque plein"
    end

    assert_raises(IOError) { job.perform(attempt) }

    attempt.reload
    assert_predicate attempt, :failed?
    assert_equal "unexpected_error", attempt.error_code
    assert_equal "disque plein", attempt.error_message
    assert_nil attempt.current_math_qualification
    assert_equal 0, SolidQueue::Job.where(class_name: "QualifyMathJob").count
  end

  test "programme la qualification seulement lorsque le document Docling est lisible" do
    attempt = create_attempt
    job = job_with(FakeClient.new(successful_result))
    storage_ready = []
    job.define_singleton_method(:enqueue_math_qualification) do |qualification|
      blob = qualification.conversion_attempt.docling_document.blob
      storage_ready << blob.service.exist?(blob.key)
      QualifyMathJob.perform_later(qualification)
    end

    job.perform(attempt)

    attempt.reload
    assert_predicate attempt, :succeeded?
    assert_equal [ true ], storage_ready
    assert_predicate attempt.current_math_qualification, :queued?
    assert_equal 1, SolidQueue::Job.where(class_name: "QualifyMathJob").count
    assert_predicate attempt.docling_document, :attached?
  end

  test "refuse de reconvertir une tentative terminée sans remplacer sa qualification" do
    attempt = create_attempt
    client = FakeClient.new(successful_result)
    job = job_with(client)
    job.perform(attempt)
    qualification_id = attempt.reload.current_math_qualification.id

    assert_raises(ConvertDocumentJob::InvalidState) { job.perform(attempt) }

    assert_equal 1, client.calls
    assert_equal qualification_id, attempt.reload.current_math_qualification.id
    assert_predicate attempt, :succeeded?
  end

  test "rend terminale une exécution interrompue redélivrée au même job" do
    attempt = create_attempt
    client = FakeClient.new(successful_result)
    job = job_with(client)
    attempt.update!(
      status: "converting",
      execution_job_id: job.job_id,
      started_at: 1.minute.ago
    )

    assert_raises(ConvertDocumentJob::InterruptedExecution) { job.perform(attempt) }

    attempt.reload
    assert_predicate attempt, :failed?
    assert_equal "interrupted_execution", attempt.error_code
    assert attempt.completed_at
    assert_equal 0, client.calls
  end

  test "ne prend pas la place d'un autre job de conversion actif" do
    attempt = create_attempt
    client = FakeClient.new(successful_result)
    attempt.update!(
      status: "converting",
      execution_job_id: "job-actif",
      started_at: 1.minute.ago
    )

    assert_raises(ConvertDocumentJob::InvalidState) do
      job_with(client).perform(attempt)
    end

    assert_predicate attempt.reload, :converting?
    assert_nil attempt.completed_at
    assert_equal 0, client.calls
  end

  test "ne prend pas une tentative déjà mise en file par un autre job" do
    attempt = create_attempt
    client = FakeClient.new(successful_result)
    attempt.update!(status: "queued", execution_job_id: "job-en-file")

    assert_raises(ConvertDocumentJob::InvalidState) do
      job_with(client).perform(attempt)
    end

    assert_predicate attempt.reload, :queued?
    assert_equal "job-en-file", attempt.execution_job_id
    assert_equal 0, client.calls
  end

  test "refuse de convertir une tentative dont le document a été supprimé" do
    attempt = create_attempt
    attempt.document.discard!
    client = FakeClient.new(successful_result)

    assert_raises(ConvertDocumentJob::InvalidState) do
      job_with(client).perform(attempt)
    end

    assert_equal 0, client.calls
    assert_predicate ConversionAttempt.unscoped.find(attempt.id), :staging?
  end

  test "n'enregistre aucun artefact si le document est supprimé pendant Docling" do
    attempt = create_attempt
    client = DiscardingClient.new(attempt, successful_result)

    assert_raises(ConvertDocumentJob::InvalidState) do
      job_with(client).perform(attempt)
    end

    stored_attempt = ConversionAttempt.unscoped.find(attempt.id)
    assert_predicate stored_attempt, :converting?
    assert_not stored_attempt.docling_response.attached?
    assert_not stored_attempt.docling_document.attached?
    assert_empty MathQualification.unscoped.where(conversion_attempt_id: attempt.id)
  end

  test "purge les artefacts si le document est supprimé pendant leur stockage" do
    attempt = create_attempt
    job = job_with(FakeClient.new(successful_result))
    original_attach = job.method(:attach)
    first_attachment = true
    job.define_singleton_method(:attach) do |attachment, content, filename, content_type|
      original_attach.call(attachment, content, filename, content_type)
      if first_attachment
        first_attachment = false
        Document.with_discarded.find(attempt.document_id).discard!
      end
    end

    assert_raises(ConvertDocumentJob::InvalidState) { job.perform(attempt) }

    stored_attempt = ConversionAttempt.unscoped.find(attempt.id)
    assert_not stored_attempt.docling_response.attached?
    assert_not stored_attempt.docling_document.attached?
    assert_empty MathQualification.unscoped.where(conversion_attempt_id: attempt.id)
  end

  test "une ancienne exécution ne peut pas écraser un état terminal" do
    attempt = create_attempt
    job = job_with(FakeClient.new(successful_result))
    attempt.update!(
      status: "failed",
      execution_job_id: job.job_id,
      error_code: "interrupted_execution",
      completed_at: Time.current
    )

    assert_raises(ConvertDocumentJob::InvalidState) do
      job.send(:persist_result!, attempt, successful_result)
    end

    assert_predicate attempt.reload, :failed?
    assert_equal "interrupted_execution", attempt.error_code
    assert_not attempt.docling_document.attached?
  end

  private

  def job_with(client)
    ConvertDocumentJob.new.tap do |job|
      job.define_singleton_method(:docling_client) { |_base_url| client }
      job.define_singleton_method(:docling_server_pool) { FakePool.new(TEST_SERVER) }
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
    attr_reader :calls, :recorded_options

    def initialize(result = nil, error: nil)
      @result = result
      @error = error
      @calls = 0
    end

    def convert(file:, filename:, options:)
      @calls += 1
      @recorded_options = options
      raise @error if @error

      @result
    end
  end

  class DiscardingClient < FakeClient
    def initialize(attempt, result)
      super(result)
      @attempt = attempt
    end

    def convert(**_arguments)
      Document.with_discarded.find(@attempt.document_id).discard!
      super
    end
  end

  class FakePool
    def initialize(server)
      @server = server
    end

    def acquire(attempt, job_id:)
      attempt.update!(
        status: "converting",
        started_at: Time.current,
        execution_job_id: job_id,
        docling_server_name: @server.name,
        docling_server_url: @server.url,
        docling_server_assigned_at: Time.current
      )
      @server
    end
  end
end
