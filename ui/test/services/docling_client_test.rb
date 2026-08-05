require "test_helper"

class DoclingClientTest < ActiveSupport::TestCase
  Response = Data.define(:code, :body)

  test "demande toutes les représentations sans simplifier la réponse" do
    transport = RecordingTransport.new(Response.new(code: "200", body: successful_body))
    client = DoclingClient.new(transport: transport)

    result = File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
      client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
    end

    assert_equal "/v1/convert/file", transport.recorded_request.path
    assert_equal "default", DoclingClient.conversion_options.fetch("vlm_pipeline_preset")
    assert_equal false, DoclingClient.conversion_options.fetch("include_images")
    assert_equal true, DoclingClient.conversion_options.fetch("include_page_images")
    assert_equal 2.0, DoclingClient.conversion_options.fetch("images_scale")
    assert_equal 86_400, DoclingClient.conversion_options.fetch("document_timeout")
    expected_fields = DoclingClient.conversion_options.transform_values do |value|
      value.is_a?(Array) ? value.map(&:to_s) : value.to_s
    end
    assert_equal expected_fields, multipart_fields(transport.recorded_request)
    assert_equal JSON.parse(successful_body), result.payload
    assert_equal successful_body, result.raw_body
  end

  test "refuse une réponse Docling incomplète" do
    body = JSON.generate(status: "success", errors: [], document: { json_content: {} })
    client = DoclingClient.new(transport: RecordingTransport.new(Response.new(code: "200", body: body)))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse un document sans inventaire de pages" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content").delete("pages")
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse un document sans image complète de page" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content").fetch("pages").fetch("1").delete("image")
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse une page sans numéro canonique" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content").fetch("pages").fetch("1").delete("page_no")
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse un inventaire de pages non contigu" do
    payload = JSON.parse(successful_body)
    page = payload.dig("document", "json_content", "pages").delete("1")
    page["page_no"] = 2
    payload.dig("document", "json_content", "pages")["2"] = page
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse un élément sans provenance canonique" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content")["texts"] = [ { "text" => "sans provenance" } ]
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "accepte et signale un texte vide sans provenance sans le modifier" do
    payload = JSON.parse(successful_body)
    empty_text = {
      "self_ref" => "#/texts/0",
      "label" => "text",
      "text" => "",
      "orig" => "",
      "prov" => [],
      "parent" => { "$ref" => "#/body" }
    }
    payload.fetch("document").fetch("json_content")["texts"] = [ empty_text ]
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )
    log = StringIO.new
    original_logger = Rails.logger
    Rails.logger = ActiveSupport::Logger.new(log)

    result = begin
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    ensure
      Rails.logger = original_logger
    end

    assert_equal empty_text, result.payload.dig("document", "json_content", "texts", 0)
    assert_includes log.string, "Docling text without provenance preserved: #/texts/0"
  end

  test "refuse un tableau vide sans provenance" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content")["tables"] = [ { "prov" => [] } ]
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse un texte vide sans provenance et sans référence canonique" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content")["texts"] = [
      { "text" => "", "orig" => "", "prov" => [] }
    ]
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse une image de page sans octets" do
    payload = JSON.parse(successful_body)
    payload.fetch("document").fetch("json_content").fetch("pages").fetch("1").fetch("image")["uri"] =
      "data:image/png;base64,"
    client = DoclingClient.new(
      transport: RecordingTransport.new(Response.new(code: "200", body: JSON.generate(payload)))
    )

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
  end

  test "refuse une racine JSON qui n'est pas un objet" do
    client = DoclingClient.new(transport: RecordingTransport.new(Response.new(code: "200", body: "null")))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "incomplete_response", error.code
    assert_equal "null", error.result.raw_body
  end

  test "normalise une erreur réseau explicite" do
    client = DoclingClient.new(transport: RaisingTransport.new(Errno::EHOSTUNREACH.new))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "network_error", error.code
  end

  test "normalise une erreur d'écriture réseau explicite" do
    client = DoclingClient.new(transport: RaisingTransport.new(Net::WriteTimeout.new("écriture interrompue")))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "network_error", error.code
  end

  test "conserve les sorties partielles d'une erreur HTTP" do
    payload = JSON.parse(successful_body).merge("status" => "failure", "errors" => [ "internal" ])
    body = JSON.generate(payload)
    client = DoclingClient.new(transport: RecordingTransport.new(Response.new(code: "500", body: body)))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "http_error", error.code
    assert_equal payload, error.result.payload
    assert_equal body, error.result.raw_body
  end

  test "conserve la réponse et les sorties partielles d'un échec Docling" do
    payload = JSON.parse(successful_body).merge("status" => "failure", "errors" => [ "timeout" ])
    body = JSON.generate(payload)
    client = DoclingClient.new(transport: RecordingTransport.new(Response.new(code: "200", body: body)))

    error = assert_raises(DoclingClient::ConversionError) do
      File.open("/reference/ostrading-environment-qualification-5-pages.pdf", "rb") do |file|
        client.convert(file: file, filename: "reference.pdf", options: DoclingClient.conversion_options)
      end
    end

    assert_equal "conversion_failed", error.code
    assert_equal payload, error.result.payload
    assert_equal body, error.result.raw_body
  end

  private

  def multipart_fields(request)
    fields = Hash.new { |hash, key| hash[key] = [] }
    request.instance_variable_get(:@body_data).each do |name, value, _options|
      fields[name] << value unless name == "files"
    end
    fields.to_h do |name, values|
      expected = DoclingClient.conversion_options.fetch(name)
      [ name, expected.is_a?(Array) ? values : values.fetch(0) ]
    end
  end

  def successful_body
    JSON.generate(
      status: "success",
      errors: [],
      processing_time: 1.25,
      document: {
        json_content: {
          schema_name: "DoclingDocument",
          pages: { "1" => { page_no: 1, image: { uri: "data:image/png;base64,iVBORw0KGgo=" } } },
          texts: [],
          tables: [],
          pictures: []
        },
        doctags_content: "<doctag>",
        html_content: "<html></html>",
        md_content: "# Titre"
      }
    )
  end

  class RecordingTransport
    attr_reader :recorded_request

    def initialize(response)
      @response = response
    end

    def request(request)
      @recorded_request = request
      @response
    end
  end

  class RaisingTransport
    def initialize(error)
      @error = error
    end

    def request(_request)
      raise @error
    end
  end
end
