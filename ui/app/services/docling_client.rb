require "json"
require "net/http"

class DoclingClient
  Result = Data.define(:payload, :raw_body)

  class ConversionError < StandardError
    attr_reader :code, :result

    def initialize(code, message, result: nil)
      @code = code
      @result = result
      super(message)
    end
  end

  REQUIRED_CONTENT = %w[json_content doctags_content html_content md_content].freeze
  NETWORK_ERRORS = [
    Net::OpenTimeout,
    Net::ReadTimeout,
    Net::WriteTimeout,
    SocketError,
    EOFError,
    Errno::ECONNREFUSED,
    Errno::ECONNRESET,
    Errno::EHOSTUNREACH,
    Errno::ENETUNREACH,
    Errno::ETIMEDOUT,
    Errno::EPIPE
  ].freeze
  STATIC_OPTIONS = {
    "from_formats" => [ "pdf" ],
    "to_formats" => %w[json doctags html md],
    "pipeline" => "vlm",
    "vlm_pipeline_preset" => "default",
    "abort_on_error" => true,
    "md_page_break_placeholder" => "<!-- page-break -->",
    "include_images" => false,
    "include_page_images" => true,
    "images_scale" => 2.0,
    "image_export_mode" => "embedded"
  }.freeze

  def self.conversion_options
    STATIC_OPTIONS.merge(
      "document_timeout" => Integer(ENV.fetch("DOCLING_DOCUMENT_TIMEOUT_SECONDS"))
    )
  end

  def initialize(transport: nil)
    @endpoint = URI.join(ENV.fetch("DOCLING_SERVE_URL"), "/v1/convert/file")
    @transport = transport || build_transport
  end

  def convert(file:, filename:, options:)
    request = Net::HTTP::Post.new(@endpoint)
    request.set_form(multipart(file, filename, options), "multipart/form-data")
    response = @transport.request(request)

    unless response.code.to_i == 200
      result = error_result(response)
      raise ConversionError.new("http_error", "Docling a refusé la conversion (HTTP #{response.code}).", result: result)
    end

    payload = JSON.parse(response.body)
    result = Result.new(payload: payload, raw_body: response.body)
    validate_payload!(result)
    result
  rescue JSON::ParserError
    result = Result.new(payload: nil, raw_body: response.body)
    raise ConversionError.new("invalid_json", "Docling a renvoyé une réponse JSON invalide.", result: result)
  rescue *NETWORK_ERRORS
    raise ConversionError.new("network_error", "La connexion à Docling a échoué.")
  end

  private

  def build_transport
    Net::HTTP.new(@endpoint.host, @endpoint.port).tap do |http|
      http.use_ssl = @endpoint.scheme == "https"
      http.open_timeout = Float(ENV.fetch("DOCLING_OPEN_TIMEOUT_SECONDS"))
      http.read_timeout = Float(ENV.fetch("DOCLING_READ_TIMEOUT_SECONDS"))
    end
  end

  def multipart(file, filename, options)
    entries = [ [ "files", file, { filename: filename, content_type: "application/pdf" } ] ]
    options.each do |name, value|
      Array(value).each { |item| entries << [ name, item.to_s ] }
    end
    entries
  end

  def validate_payload!(result)
    payload = result.payload
    unless payload.is_a?(Hash)
      raise ConversionError.new("incomplete_response", "La réponse Docling est incomplète.", result: result)
    end

    unless payload["status"] == "success" && payload["errors"] == []
      raise ConversionError.new("conversion_failed", "Docling signale l’échec de la conversion.", result: result)
    end

    unless valid_document?(payload["document"])
      raise ConversionError.new("incomplete_response", "La réponse Docling est incomplète.", result: result)
    end
  end

  def error_result(response)
    Result.new(payload: JSON.parse(response.body), raw_body: response.body)
  rescue JSON::ParserError
    Result.new(payload: nil, raw_body: response.body)
  end

  def valid_document?(document)
    return false unless document.is_a?(Hash)

    content = document["json_content"]
    return false unless content.is_a?(Hash) && valid_pages?(content["pages"])

    page_numbers = content.fetch("pages").values.map { |page| page.fetch("page_no") }
    valid_items?(content, page_numbers) &&
      REQUIRED_CONTENT.drop(1).all? { |name| document[name].is_a?(String) }
  end

  def valid_pages?(pages)
    pages.is_a?(Hash) && pages.any? && pages.all? do |key, page|
      page_number = page["page_no"] if page.is_a?(Hash)
      image_uri = page.dig("image", "uri") if page.is_a?(Hash)
      page_number.is_a?(Integer) && page_number.positive? && key == page_number.to_s &&
        image_uri.is_a?(String) &&
        image_uri.match?(/\Adata:image\/[a-z0-9.+-]+;base64,[a-z0-9+\/=]+\z/i)
    end
  end

  def valid_items?(content, page_numbers)
    %w[texts tables pictures].all? do |name|
      items = content[name]
      items.is_a?(Array) && items.all? do |item|
        provenance = item["prov"] if item.is_a?(Hash)
        provenance.is_a?(Array) && provenance.any? && provenance.all? do |entry|
          entry.is_a?(Hash) && page_numbers.include?(entry["page_no"])
        end
      end
    end
  end
end
