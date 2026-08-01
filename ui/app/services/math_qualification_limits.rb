class MathQualificationLimits
  class Exceeded < StandardError
    attr_reader :code

    def initialize(code, message)
      @code = code
      super(message)
    end
  end

  def initialize(response_bytes:, artifact_bytes:, report_bytes:, event_bytes:)
    @response_bytes = positive!(response_bytes, "flux")
    @artifact_bytes = positive!(artifact_bytes, "artefacts")
    @report_bytes = positive!(report_bytes, "rapport")
    @event_bytes = positive!(event_bytes, "événement")
  end

  def append_raw!(raw, chunk)
    remaining = @response_bytes - raw.bytesize
    raw << chunk.byteslice(0, remaining) if remaining.positive?
    return if chunk.bytesize <= remaining

    exceed!("response_too_large", "Le flux de l’analyseur dépasse la limite configurée.")
  end

  def validate_event!(bytes)
    return if bytes <= @event_bytes

    exceed!("event_too_large", "Un événement de l’analyseur dépasse la limite configurée.")
  end

  def append_artifact!(artifacts, name, content)
    artifact_remaining = @artifact_bytes - artifacts.values.sum(&:bytesize)
    report_remaining = @report_bytes - artifacts.fetch("report").bytesize
    remaining = name == "report" ? [ artifact_remaining, report_remaining ].min : artifact_remaining
    artifacts.fetch(name) << content.byteslice(0, remaining) if remaining.positive?
    return if content.bytesize <= remaining

    if name == "report" && report_remaining <= artifact_remaining
      exceed!("report_too_large", "Le rapport de l’analyseur dépasse la limite configurée.")
    end
    exceed!("artifact_too_large", "Les artefacts de l’analyseur dépassent la limite configurée.")
  end

  private

  def positive!(value, label)
    raise ArgumentError, "La limite #{label} doit être positive." unless value.positive?

    value
  end

  def exceed!(code, message)
    raise Exceeded.new(code, message)
  end
end
