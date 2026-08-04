require "base64"
require "digest"
require "json"
require "net/http"

class MathQualificationClient
  Result = Data.define(
    :raw_response,
    :report,
    :report_bytes,
    :evidence,
    :corrections,
    :correction_evidence,
    :derived_docling_document,
    :derived_html,
    :derived_markdown,
    :native_page_html
  )

  class QualificationError < StandardError
    attr_reader :code, :result

    def initialize(code, message, result: nil)
      @code = code
      @result = result
      super(message)
    end
  end

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
  REQUIRED_ARTIFACT_NAMES = %w[
    evidence corrections correction_evidence native_page_html report
  ].freeze
  DERIVED_ARTIFACT_NAMES = %w[derived_docling_document derived_html derived_markdown].freeze
  ARTIFACT_NAMES = (REQUIRED_ARTIFACT_NAMES + DERIVED_ARTIFACT_NAMES).freeze
  PROGRESS_PHASES = %w[
    source_analysis docling_alignment candidate_evaluation correction_proposal correction_export
  ].freeze

  def initialize(
    transport: nil,
    max_response_bytes: Integer(ENV.fetch("MATH_AUDIT_MAX_RESPONSE_BYTES")),
    max_artifact_bytes: Integer(ENV.fetch("MATH_AUDIT_MAX_ARTIFACT_BYTES")),
    max_report_bytes: Integer(ENV.fetch("MATH_AUDIT_MAX_REPORT_BYTES")),
    max_event_bytes: Integer(ENV.fetch("MATH_AUDIT_MAX_EVENT_BYTES"))
  )
    @endpoint = URI.join(ENV.fetch("MATH_AUDIT_URL"), "/v1/qualifications")
    @transport = transport || build_transport
    @limits = MathQualificationLimits.new(
      response_bytes: max_response_bytes,
      artifact_bytes: max_artifact_bytes,
      report_bytes: max_report_bytes,
      event_bytes: max_event_bytes
    )
  end

  def qualify(source_file:, source_filename:, document_file:, source_sha256:, docling_document_sha256:)
    request = Net::HTTP::Post.new(@endpoint)
    request.set_form(
      multipart(
        source_file,
        source_filename,
        document_file,
        source_sha256,
        docling_document_sha256
      ),
      "multipart/form-data"
    )
    consume(request) { |progress| yield progress }
  end

  private

  def build_transport
    Net::HTTP.new(@endpoint.host, @endpoint.port).tap do |http|
      http.use_ssl = @endpoint.scheme == "https"
      http.open_timeout = Float(ENV.fetch("MATH_AUDIT_OPEN_TIMEOUT_SECONDS"))
      http.read_timeout = Float(ENV.fetch("MATH_AUDIT_READ_TIMEOUT_SECONDS"))
    end
  end

  def multipart(source, filename, document, source_sha256, document_sha256)
    [
      [ "source_pdf", source, { filename: filename, content_type: "application/pdf" } ],
      [ "docling_document", document, { filename: "document.json", content_type: "application/json" } ],
      [ "source_sha256", source_sha256 ],
      [ "docling_document_sha256", document_sha256 ],
      [ "contract_version", MathQualification::CONTRACT_VERSION ],
      [ "capability_profile", MathQualification::CAPABILITY_PROFILE ]
    ]
  end

  def consume(request)
    raw = +"".b
    artifacts = ARTIFACT_NAMES.to_h { |name| [ name, +"".b ] }
    sequences = ARTIFACT_NAMES.to_h { |name| [ name, 0 ] }
    progress_state = { phase: -1, completed: 0, total: 0 }
    terminal = nil
    @transport.request(request) do |response|
      unless response.code.to_i == 200
        response.read_body { |chunk| @limits.append_raw!(raw, chunk) }
        raise QualificationError.new("http_error", "L’analyseur mathématique a refusé la requête (HTTP #{response.code}).", result: partial(raw, artifacts))
      end

      buffer = +"".b
      response.read_body do |chunk|
        @limits.append_raw!(raw, chunk)
        buffer << chunk
        while (newline = buffer.index("\n"))
          @limits.validate_event!(newline + 1)
          line = buffer.slice!(0..newline)
          terminal = consume_event(
            JSON.parse(line),
            terminal,
            artifacts,
            sequences,
            raw,
            progress_state
          ) { |progress| yield progress }
        end
        @limits.validate_event!(buffer.bytesize)
      end
      invalid!(raw, artifacts, "Le flux NDJSON se termine au milieu d’un événement.") unless buffer.empty?
    end
    invalid!(raw, artifacts, "Le flux ne contient pas de résultat terminal.") unless terminal&.fetch("type") == "result"
    validate_artifacts!(terminal.fetch("artifacts"), artifacts, sequences, raw)
    report = JSON.parse(artifacts.fetch("report"))
    invalid!(raw, artifacts, "Le rapport terminal n’est pas un objet JSON.") unless report.is_a?(Hash)
    build_result(
      raw,
      artifacts,
      report: report
    )
  rescue *NETWORK_ERRORS
    raise QualificationError.new(
      "network_error",
      "La connexion à l’analyseur mathématique a échoué.",
      result: partial(raw, artifacts)
    )
  rescue MathQualificationLimits::Exceeded => error
    raise QualificationError.new(
      error.code,
      error.message,
      result: partial(raw, artifacts)
    )
  rescue JSON::ParserError, KeyError, ArgumentError => error
    invalid!(raw, artifacts, "Flux NDJSON invalide : #{error.message}")
  end

  def build_result(raw, artifacts, report:)
    Result.new(
      raw_response: raw,
      report: report,
      report_bytes: artifacts.fetch("report"),
      evidence: artifacts.fetch("evidence"),
      corrections: artifacts.fetch("corrections"),
      correction_evidence: artifacts.fetch("correction_evidence"),
      derived_docling_document: artifacts.fetch("derived_docling_document"),
      derived_html: artifacts.fetch("derived_html"),
      derived_markdown: artifacts.fetch("derived_markdown"),
      native_page_html: artifacts.fetch("native_page_html")
    )
  end

  def consume_event(event, terminal, artifacts, sequences, raw, progress_state)
    invalid!(raw, artifacts, "Un événement NDJSON doit être un objet.") unless event.is_a?(Hash)
    invalid!(raw, artifacts, "Un événement suit l’événement terminal.") if terminal
    case event.fetch("type")
    when "progress"
      validate_progress!(event, progress_state)
      yield event
      nil
    when "artifact"
      name = event.fetch("name")
      invalid!(raw, artifacts, "Artefact inconnu : #{name}") unless ARTIFACT_NAMES.include?(name)
      sequence = event.fetch("sequence")
      content = event.fetch("content_base64")
      invalid!(raw, artifacts, "Séquence de fragments invalide.") unless sequence.is_a?(Integer)
      invalid!(raw, artifacts, "Fragment base64 invalide.") unless content.is_a?(String)
      invalid!(raw, artifacts, "Séquence de fragments discontinue.") unless sequence == sequences.fetch(name)
      @limits.append_artifact!(artifacts, name, Base64.strict_decode64(content))
      sequences[name] += 1
      nil
    when "error"
      code = event.fetch("code")
      message = event.fetch("message")
      invalid!(raw, artifacts, "Erreur terminale invalide.") unless code.is_a?(String) && message.is_a?(String)
      raise QualificationError.new(code, message, result: partial(raw, artifacts))
    when "result"
      event
    else
      invalid!(raw, artifacts, "Type d’événement inconnu.")
    end
  end

  def validate_progress!(event, previous)
    phase = PROGRESS_PHASES.index(event["phase"])
    valid = phase &&
      event["completed_units"].is_a?(Integer) &&
      event["total_units"].is_a?(Integer) &&
      event["total_units"] >= 0 &&
      event["completed_units"].between?(0, event["total_units"]) &&
      phase >= previous.fetch(:phase) &&
      (phase > previous.fetch(:phase) || (
        event["total_units"] == previous.fetch(:total) &&
        event["completed_units"] >= previous.fetch(:completed)
      ))
    raise ArgumentError, "Progression invalide" unless valid

    previous.update(
      phase: phase,
      completed: event.fetch("completed_units"),
      total: event.fetch("total_units")
    )
  end

  def validate_artifacts!(metadata, artifacts, sequences, raw)
    invalid!(raw, artifacts, "Inventaire d’artefacts invalide.") unless metadata.is_a?(Hash)
    names = metadata.keys
    valid_names = (names - ARTIFACT_NAMES).empty? &&
      (REQUIRED_ARTIFACT_NAMES - names).empty? &&
      ((names & DERIVED_ARTIFACT_NAMES).empty? || (DERIVED_ARTIFACT_NAMES - names).empty?)
    invalid!(raw, artifacts, "Inventaire d’artefacts invalide.") unless valid_names
    names.each do |name|
      expected = metadata.fetch(name)
      content = artifacts.fetch(name)
      valid = expected.is_a?(Hash) &&
        expected.fetch("bytes") == content.bytesize &&
        expected.fetch("chunks") == sequences.fetch(name) &&
        expected.fetch("sha256") == Digest::SHA256.hexdigest(content)
      invalid!(raw, artifacts, "Empreinte ou taille invalide pour #{name}.") unless valid
    end
  end

  def partial(raw, artifacts)
    report = JSON.parse(artifacts.fetch("report")) unless artifacts.fetch("report").empty?
    build_result(raw, artifacts, report: report)
  rescue JSON::ParserError
    build_result(raw, artifacts, report: nil)
  end

  def invalid!(raw, artifacts, message)
    raise QualificationError.new("invalid_stream", message, result: partial(raw, artifacts))
  end
end
