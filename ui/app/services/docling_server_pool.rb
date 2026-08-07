require "json"
require "set"
require "uri"

class DoclingServerPool
  Server = Data.define(:name, :url, :priority)
  LOCK_ID = 1_541_788_247

  class ConfigurationError < StandardError; end
  class InvalidAttempt < StandardError; end

  def initialize(
    servers: self.class.configured_servers,
    poll_interval: Float(ENV.fetch("DOCLING_CAPACITY_POLL_SECONDS")),
    sleeper: Kernel
  )
    @servers = servers.sort_by(&:priority)
    @poll_interval = Float(poll_interval)
    @sleeper = sleeper
    unless @poll_interval.positive? && @poll_interval.finite?
      raise ConfigurationError, "DOCLING_CAPACITY_POLL_SECONDS doit être positif et fini."
    end
  rescue ArgumentError, TypeError
    raise ConfigurationError, "DOCLING_CAPACITY_POLL_SECONDS doit être positif et fini."
  end

  def self.configured_servers
    entries = JSON.parse(ENV.fetch("DOCLING_SERVERS"))
    raise ConfigurationError, "DOCLING_SERVERS doit contenir au moins un serveur." unless entries.is_a?(Array) && entries.any?

    servers = entries.map do |entry|
      raise ConfigurationError, "Chaque serveur Docling doit être un objet." unless entry.is_a?(Hash)

      name = entry.fetch("name")
      url = canonical_url(entry.fetch("url"))
      priority = Integer(entry.fetch("priority"))
      unless name.is_a?(String) && name.present? && priority.positive? &&
        url
        raise ConfigurationError, "Configuration de serveur Docling invalide."
      end

      Server.new(name: name, url: url, priority: priority)
    end
    validate_uniqueness!(servers)
    servers.sort_by(&:priority)
  rescue JSON::ParserError, KeyError, ArgumentError, TypeError, URI::InvalidURIError => error
    raise ConfigurationError, "DOCLING_SERVERS est invalide : #{error.message}"
  end

  def self.validate_uniqueness!(servers)
    names = servers.map(&:name)
    priorities = servers.map(&:priority)
    urls = servers.map(&:url)
    return if names.uniq.size == names.size && priorities.uniq.size == priorities.size &&
      urls.uniq.size == urls.size

    raise ConfigurationError, "Les noms, URL et priorités des serveurs Docling doivent être uniques."
  end
  private_class_method :validate_uniqueness!

  def self.canonical_url(value)
    uri = URI.parse(value)
    return unless uri.is_a?(URI::HTTP) && uri.host.present? && uri.userinfo.nil? &&
      uri.port.between?(1, 65_535) && [ "", "/" ].include?(uri.path) &&
      uri.query.nil? && uri.fragment.nil?

    uri.class.build(
      scheme: uri.scheme.downcase,
      host: uri.host.downcase,
      port: uri.port == uri.default_port ? nil : uri.port
    ).to_s
  end
  private_class_method :canonical_url

  def acquire(attempt, job_id:)
    loop do
      server = reserve_first_available(attempt, job_id)
      return server if server

      @sleeper.sleep(@poll_interval)
    end
  end

  private

  def reserve_first_available(attempt, job_id)
    selected = nil
    ConversionAttempt.transaction do
      lock_scheduler!
      attempt.lock!
      ensure_waiting_for!(attempt, job_id)

      unresolved_assignments = ConversionAttempt
        .where(docling_server_returned_at: nil)
        .where.not(id: attempt.id)
      busy_names = unresolved_assignments.where(docling_server_name: @servers.map(&:name))
        .pluck(:docling_server_name).to_set
      busy_urls = unresolved_assignments.where(docling_server_url: @servers.map(&:url))
        .pluck(:docling_server_url).to_set
      active_attempts = ConversionAttempt.where(status: "converting").where.not(id: attempt.id)
      unless active_attempts.where(docling_server_name: nil).exists?
        selected = @servers.find do |server|
          !busy_names.include?(server.name) && !busy_urls.include?(server.url)
        end
      end
      if selected
        attempt.update!(
          status: "converting",
          started_at: Time.current,
          execution_job_id: job_id,
          docling_server_name: selected.name,
          docling_server_url: selected.url,
          docling_server_assigned_at: Time.current
        )
      end
    end
    selected
  end

  def lock_scheduler!
    ConversionAttempt.connection.execute("SELECT pg_advisory_xact_lock(#{LOCK_ID})")
  end

  def ensure_waiting_for!(attempt, job_id)
    unless Document.with_discarded.find_by(id: attempt.document_id)&.kept?
      raise InvalidAttempt, "La tentative appartient à un document supprimé."
    end

    return if (attempt.staging? || attempt.queued?) &&
      (attempt.execution_job_id.blank? || attempt.execution_job_id == job_id)

    raise InvalidAttempt, "La tentative #{attempt.id} n'est plus disponible pour ce job."
  end
end
