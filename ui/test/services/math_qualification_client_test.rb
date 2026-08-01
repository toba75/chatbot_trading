require "base64"
require "digest"
require "test_helper"

class MathQualificationClientTest < ActiveSupport::TestCase
  Response = Data.define(:code, :chunks) do
    def read_body
      chunks.each { |chunk| yield chunk }
    end
  end

  test "reconstruit les artefacts et publie chaque progression dans l'ordre" do
    report = JSON.generate(status: "completed")
    evidence = "preuve".b
    response = Response.new(code: "200", chunks: split_stream(success_events(report, evidence)))
    transport = StreamingTransport.new(response)
    progress = []

    result = files do |source, document|
      client(transport).qualify(
        source_file: source,
        source_filename: "source.pdf",
        document_file: document,
        source_sha256: "a" * 64,
        docling_document_sha256: "b" * 64
      ) { |event| progress << event }
    end

    assert_equal [ "source_analysis" ], progress.pluck("phase")
    assert_equal JSON.parse(report), result.report
    assert_equal report, result.report_bytes
    assert_equal evidence, result.evidence
    assert_equal success_events(report, evidence), result.raw_response
    assert_equal "/v1/qualifications", transport.recorded_request.path
  end

  test "refuse une séquence de fragments discontinue" do
    events = [
      { type: "artifact", name: "report", sequence: 1, content_base64: Base64.strict_encode64("{}") },
      { type: "result", artifacts: {} }
    ].map { |event| JSON.generate(event) }.join("\n") + "\n"

    error = assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(Response.new(code: "200", chunks: [ events ]))).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_event| }
      end
    end

    assert_equal "invalid_stream", error.code
  end

  test "conserve le flux et les fragments reçus lors d'un échec terminal" do
    raw = [
      { type: "artifact", name: "evidence", sequence: 0, content_base64: Base64.strict_encode64("partiel") },
      { type: "error", code: "analysis_failed", message: "Analyse impossible." }
    ].map { |event| JSON.generate(event) }.join("\n") + "\n"

    error = assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(Response.new(code: "200", chunks: [ raw ]))).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_event| }
      end
    end

    assert_equal "analysis_failed", error.code
    assert_equal "partiel", error.result.evidence
    assert_equal raw, error.result.raw_response
  end

  test "refuse une progression qui régresse" do
    raw = [
      { type: "progress", phase: "source_analysis", completed_units: 1, total_units: 2 },
      { type: "progress", phase: "source_analysis", completed_units: 0, total_units: 2 }
    ].map { |event| JSON.generate(event) }.join("\n") + "\n"

    error = assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(Response.new(code: "200", chunks: [ raw ]))).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_event| }
      end
    end

    assert_equal "invalid_stream", error.code
  end

  test "conserve le flux et les artefacts partiels lors d'une coupure réseau" do
    event = JSON.generate(
      type: "artifact",
      name: "evidence",
      sequence: 0,
      content_base64: Base64.strict_encode64("preuve partielle")
    ) + "\n"
    response = InterruptingResponse.new(code: "200", first_chunk: event)

    error = assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(response)).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_progress| }
      end
    end

    assert_equal "network_error", error.code
    assert_equal event, error.result.raw_response
    assert_equal "preuve partielle", error.result.evidence
  end

  test "refuse explicitement un inventaire d'artefacts qui n'est pas un objet" do
    raw = JSON.generate(type: "result", artifacts: []) + "\n"

    error = assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(Response.new(code: "200", chunks: [ raw ]))).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_progress| }
      end
    end

    assert_equal "invalid_stream", error.code
    assert_equal raw, error.result.raw_response
  end

  test "refuse explicitement un événement NDJSON qui n'est pas un objet" do
    raw = "[]\n"

    error = qualification_error_for(raw)

    assert_equal "invalid_stream", error.code
    assert_equal raw, error.result.raw_response
  end

  test "refuse explicitement un fragment base64 qui n'est pas une chaîne" do
    raw = JSON.generate(
      type: "artifact",
      name: "report",
      sequence: 0,
      content_base64: 12
    ) + "\n"

    error = qualification_error_for(raw)

    assert_equal "invalid_stream", error.code
    assert_equal raw, error.result.raw_response
  end

  test "borne le flux brut en conservant le préfixe reçu" do
    raw = JSON.generate(type: "progress", phase: "source_analysis", completed_units: 0, total_units: 1) + "\n"
    limit = raw.bytesize - 3

    error = qualification_error_for(raw, max_response_bytes: limit)

    assert_equal "response_too_large", error.code
    assert_equal raw.byteslice(0, limit), error.result.raw_response
  end

  test "borne le total des artefacts en conservant les octets admis" do
    raw = JSON.generate(
      type: "artifact",
      name: "evidence",
      sequence: 0,
      content_base64: Base64.strict_encode64("preuve")
    ) + "\n"

    error = qualification_error_for(raw, max_artifact_bytes: 4)

    assert_equal "artifact_too_large", error.code
    assert_equal "preu", error.result.evidence
    assert_equal raw, error.result.raw_response
  end

  test "borne le rapport avant sa matérialisation en objets Ruby" do
    raw = JSON.generate(
      type: "artifact",
      name: "report",
      sequence: 0,
      content_base64: Base64.strict_encode64('{"regions":[]}')
    ) + "\n"

    error = qualification_error_for(raw, max_report_bytes: 4)

    assert_equal "report_too_large", error.code
    assert_equal '{"re', error.result.report_bytes
    assert_nil error.result.report
  end

  test "borne chaque événement avant son parsing JSON" do
    raw = JSON.generate(type: "progress", padding: "x" * 20) + "\n"

    error = qualification_error_for(raw, max_event_bytes: 16)

    assert_equal "event_too_large", error.code
    assert_equal raw, error.result.raw_response
  end

  private

  def qualification_error_for(raw, **limits)
    assert_raises(MathQualificationClient::QualificationError) do
      files do |source, document|
        client(StreamingTransport.new(Response.new(code: "200", chunks: [ raw ])), **limits).qualify(
          source_file: source,
          source_filename: "source.pdf",
          document_file: document,
          source_sha256: "a" * 64,
          docling_document_sha256: "b" * 64
        ) { |_progress| }
      end
    end
  end

  def client(transport, **limits)
    MathQualificationClient.new(transport: transport, **limits)
  end

  def files
    Tempfile.create([ "source", ".pdf" ]) do |source|
      Tempfile.create([ "document", ".json" ]) do |document|
        yield source, document
      end
    end
  end

  def success_events(report, evidence)
    artifacts = { "report" => report.b, "evidence" => evidence }
    events = [
      { type: "progress", phase: "source_analysis", completed_units: 1, total_units: 1 }
    ]
    metadata = {}
    artifacts.each do |name, content|
      content.bytes.each_slice(4).with_index do |bytes, sequence|
        events << {
          type: "artifact",
          name: name,
          sequence: sequence,
          content_base64: Base64.strict_encode64(bytes.pack("C*"))
        }
      end
      metadata[name] = {
        bytes: content.bytesize,
        sha256: Digest::SHA256.hexdigest(content),
        chunks: (content.bytesize / 4.0).ceil
      }
    end
    events << { type: "result", artifacts: metadata }
    events.map { |event| JSON.generate(event) }.join("\n") + "\n"
  end

  def split_stream(stream)
    [ stream.byteslice(0, 17), stream.byteslice(17, 31), stream.byteslice(48..) ]
  end

  class StreamingTransport
    attr_reader :recorded_request

    def initialize(response)
      @response = response
    end

    def request(request)
      @recorded_request = request
      yield @response
    end
  end

  InterruptingResponse = Data.define(:code, :first_chunk) do
    def read_body
      yield first_chunk
      raise EOFError, "connexion interrompue"
    end
  end
end
