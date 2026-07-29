require "test_helper"

class DocumentTest < ActiveSupport::TestCase
  REFERENCE_PDF = "/reference/ostrading-environment-qualification-5-pages.pdf"

  test "conserve exactement un PDF valide et son identité" do
    document = Document.create_from_pdf!(uploaded_file(REFERENCE_PDF))

    assert_equal Digest::SHA256.file(REFERENCE_PDF).hexdigest, document.source_sha256
    assert_equal File.binread(REFERENCE_PDF), document.source_pdf.download
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

  private

  def uploaded_file(path, filename: File.basename(path), type: "application/pdf")
    tempfile = Tempfile.new([ "upload", File.extname(path) ])
    File.open(path, "rb") { |source| IO.copy_stream(source, tempfile) }
    tempfile.rewind

    ActionDispatch::Http::UploadedFile.new(tempfile: tempfile, filename: filename, type: type)
  end
end
