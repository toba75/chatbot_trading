require "ui_system_test_case"

class DocumentInterfaceTest < UiSystemTestCase
  test "le lien d'une page vide ouvre directement cette page dans le lecteur PDF" do
    document = completed_reference_document

    visit document_path(document)
    find(".conversion-warning a", text: "5").click

    assert_selector %(canvas[data-rendered-page="5"])
    assert_field "Page", with: "5"
    assert_no_text "Pages canoniques"
    assert_no_selector ".quality-summary"
  end

  private

  def completed_reference_document
    upload = Rack::Test::UploadedFile.new(unique_reference_pdf, "application/pdf", true)
    document = Document.create_from_pdf!(upload)
    attempt = document.start_conversion!(conversion_options: DoclingClient.conversion_options)
    content = {
      "pages" => (1..5).to_h { |page| [ page.to_s, { "page_no" => page } ] },
      "texts" => (1..4).map { |page| { "prov" => [ { "page_no" => page } ] } },
      "tables" => [],
      "pictures" => []
    }
    attempt.docling_document.attach(
      io: StringIO.new(JSON.generate(content)),
      filename: "document.json",
      content_type: "application/json"
    )
    attempt.html.attach(
      io: StringIO.new("<html><body>conversion</body></html>"),
      filename: "document.html",
      content_type: "text/html"
    )
    attempt.markdown.attach(
      io: StringIO.new("conversion"),
      filename: "document.md",
      content_type: "text/markdown"
    )
    attempt.update!(status: "succeeded", page_count: 5, completed_at: Time.current)
    document
  end

  def unique_reference_pdf
    source = File.binread("/reference/ostrading-environment-qualification-5-pages.pdf")
    path = Rails.root.join("tmp", "interface-#{SecureRandom.hex(8)}.pdf")
    File.binwrite(path, "#{source}\n% ui-test #{SecureRandom.uuid}\n")
    path
  end
end
