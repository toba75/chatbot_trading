require "test_helper"

class DocumentTest < ActiveSupport::TestCase
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"

  test "conserve exactement un PDF valide et son identité" do
    document = Document.create_from_pdf!(uploaded_file(REFERENCE_PDF))

    assert_equal Digest::SHA256.file(REFERENCE_PDF).hexdigest, document.source_sha256
    assert_equal File.binread(REFERENCE_PDF), document.source_pdf.download
  end

  test "refuse deux PDFs identiques même si leur nom diffère" do
    Document.create_from_pdf!(uploaded_file(REFERENCE_PDF, filename: "original.pdf"))

    assert_raises(ActiveRecord::RecordInvalid) do
      Document.create_from_pdf!(uploaded_file(REFERENCE_PDF, filename: "copie.pdf"))
    end
    assert_equal 1, Document.count
  end

  test "valide toujours le PDF même si une identité SHA-256 est fournie" do
    file = Tempfile.new([ "not-a-pdf", ".pdf" ])
    file.write("texte")
    file.rewind

    error = assert_raises(Document::InvalidPdf) do
      Document.create_from_pdf!(uploaded_file(file.path), source_sha256: "a" * 64)
    end

    assert_equal "Le fichier ne possède pas la signature d’un PDF.", error.message
    assert_equal 0, Document.count
  ensure
    file.close!
  end

  test "refuse un fichier dont la signature n'est pas celle d'un PDF" do
    file = Tempfile.new([ "not-a-pdf", ".pdf" ])
    file.write("texte")
    file.rewind

    error = assert_raises(Document::InvalidPdf) do
      Document.create_from_pdf!(uploaded_file(file.path))
    end

    assert_equal "Le fichier ne possède pas la signature d’un PDF.", error.message
    assert_equal 0, Document.count
  ensure
    file.close!
  end

  test "refuse une extension différente de pdf" do
    error = assert_raises(Document::InvalidPdf) do
      Document.create_from_pdf!(uploaded_file(REFERENCE_PDF, filename: "document.txt"))
    end

    assert_equal "Le fichier doit porter l’extension .pdf.", error.message
  end

  test "refuse un type MIME différent de application/pdf" do
    error = assert_raises(Document::InvalidPdf) do
      Document.create_from_pdf!(uploaded_file(REFERENCE_PDF, type: "text/plain"))
    end

    assert_equal "Le fichier doit être déclaré comme un PDF.", error.message
  end

  test "refuse un PDF au-delà de la taille configurée" do
    file = Tempfile.new([ "large", ".pdf" ])
    file.write("%PDF-")
    file.truncate(Integer(ENV.fetch("PDF_MAX_BYTES")) + 1)
    file.rewind

    error = assert_raises(Document::InvalidPdf) do
      Document.create_from_pdf!(uploaded_file(file.path))
    end

    assert_equal "Le PDF dépasse la taille maximale autorisée.", error.message
  ensure
    file.close!
  end

  test "distingue les statuts de conversion et de qualification" do
    document = Document.create_from_pdf!(uploaded_file(REFERENCE_PDF))
    attempt = document.start_conversion!(conversion_options: { "pipeline" => "vlm" })

    assert_equal({ key: "conversion_staging", label: "Préparation" }, document.processing_status)

    attempt.update!(status: "succeeded", completed_at: Time.current)
    assert_equal({ key: "qualification_missing", label: "Qualification à programmer" }, document.processing_status)

    qualification = MathQualification.build_for(attempt, docling_document_sha256: "b" * 64)
    qualification.save!
    assert_equal(
      { key: "qualification_staging", label: "Préparation de la qualification" },
      document.processing_status
    )

    qualification.update!(status: "queued", execution_job_id: "qualification-job")
    assert_equal({ key: "qualification_queued", label: "Qualification en attente" }, document.processing_status)

    qualification.update!(
      status: "running",
      phase: "source_analysis",
      started_at: Time.current
    )
    assert_equal({ key: "qualification_running", label: "Qualification en cours" }, document.processing_status)

    qualification.update!(
      status: "failed",
      error_code: "analysis_failed",
      completed_at: Time.current
    )
    assert_equal({ key: "qualification_failed", label: "Échec qualification" }, document.processing_status)
  end

  test "déclare le document terminé seulement après une qualification réussie" do
    document = Document.create_from_pdf!(uploaded_file(REFERENCE_PDF))
    attempt = document.start_conversion!(conversion_options: { "pipeline" => "vlm" })
    attempt.update!(status: "succeeded", completed_at: Time.current)
    qualification = MathQualification.build_for(attempt, docling_document_sha256: "b" * 64)
    qualification.save!

    qualification.update!(
      status: "succeeded",
      phase: "persisting_result",
      completed_units: 1,
      total_units: 1,
      verdict: "non_verifiable",
      summary: { "regions" => 0 },
      completed_at: Time.current
    )

    assert_equal({ key: "completed", label: "Terminé" }, document.processing_status)
  end

  private

  def uploaded_file(path, filename: File.basename(path), type: "application/pdf")
    tempfile = Tempfile.new([ "upload", File.extname(path) ])
    File.open(path, "rb") { |source| IO.copy_stream(source, tempfile) }
    tempfile.rewind

    ActionDispatch::Http::UploadedFile.new(tempfile: tempfile, filename: filename, type: type)
  end
end
