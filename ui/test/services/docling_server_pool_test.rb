require "test_helper"

class DoclingServerPoolTest < ActiveSupport::TestCase
  REMOTE = DoclingServerPool::Server.new(
    name: "remote", url: "http://docling-remote.test:5001", priority: 1
  )
  LOCAL = DoclingServerPool::Server.new(
    name: "local", url: "http://docling-local.test:5001", priority: 2
  )

  test "réserve le serveur prioritaire lorsqu'il est libre" do
    attempt = waiting_attempt("job-prioritaire")

    server = pool.acquire(attempt, job_id: "job-prioritaire")

    assert_equal REMOTE, server
    assert_assignment attempt.reload, REMOTE
  end

  test "réserve le serveur suivant lorsque le prioritaire traite déjà un job" do
    active_attempt(REMOTE, "job-distant")
    attempt = waiting_attempt("job-local")

    server = pool.acquire(attempt, job_id: "job-local")

    assert_equal LOCAL, server
    assert_assignment attempt.reload, LOCAL
  end

  test "un échec sans retour conserve la capacité du serveur" do
    unresolved = active_attempt(REMOTE, "job-sans-retour")
    unresolved.update!(status: "failed", completed_at: Time.current)
    attempt = waiting_attempt("job-suivant")

    server = pool.acquire(attempt, job_id: "job-suivant")

    assert_equal LOCAL, server
    assert_assignment attempt.reload, LOCAL
  end

  test "un retour terminal libère la capacité du serveur" do
    returned = active_attempt(REMOTE, "job-avec-retour")
    returned.update!(
      status: "succeeded",
      completed_at: Time.current,
      docling_server_returned_at: Time.current
    )
    attempt = waiting_attempt("job-suivant")

    server = pool.acquire(attempt, job_id: "job-suivant")

    assert_equal REMOTE, server
    assert_assignment attempt.reload, REMOTE
  end

  test "un renommage ne libère pas une URL encore occupée" do
    active_attempt(REMOTE, "job-ancien-nom")
    renamed_remote = DoclingServerPool::Server.new(
      name: "remote-renamed", url: REMOTE.url, priority: 1
    )
    attempt = waiting_attempt("job-nouveau-nom")
    renamed_pool = DoclingServerPool.new(
      servers: [ renamed_remote, LOCAL ],
      poll_interval: 0.001,
      sleeper: ReleasingSleeper.new
    )

    server = renamed_pool.acquire(attempt, job_id: "job-nouveau-nom")

    assert_equal LOCAL, server
    assert_assignment attempt.reload, LOCAL
  end

  test "attend puis reprend le premier serveur libéré selon la priorité" do
    remote_attempt = active_attempt(REMOTE, "job-distant")
    active_attempt(LOCAL, "job-local")
    attempt = waiting_attempt("job-en-attente")
    sleeper = ReleasingSleeper.new do
      remote_attempt.update!(
        status: "succeeded",
        completed_at: Time.current,
        docling_server_returned_at: Time.current
      )
    end

    server = pool(sleeper: sleeper).acquire(attempt, job_id: "job-en-attente")

    assert_equal 1, sleeper.calls
    assert_equal REMOTE, server
    assert_assignment attempt.reload, REMOTE
  end

  test "une conversion historique sans destination bloque toute nouvelle affectation" do
    unknown = document("inconnue").conversion_attempts.create!(
      status: "converting",
      conversion_options: { "pipeline" => "vlm" },
      execution_job_id: "job-inconnu",
      started_at: Time.current
    )
    attempt = waiting_attempt("job-en-attente")
    sleeper = ReleasingSleeper.new do
      unknown.update!(status: "failed", completed_at: Time.current)
    end

    server = pool(sleeper: sleeper).acquire(attempt, job_id: "job-en-attente")

    assert_equal 1, sleeper.calls
    assert_equal REMOTE, server
  end

  test "refuse une configuration dont les priorités ne sont pas uniques" do
    configuration = JSON.generate([
      { name: "remote", url: REMOTE.url, priority: 1 },
      { name: "local", url: LOCAL.url, priority: 1 }
    ])

    previous_configuration = ENV["DOCLING_SERVERS"]
    ENV["DOCLING_SERVERS"] = configuration
    error = begin
      assert_raises(DoclingServerPool::ConfigurationError) do
        DoclingServerPool.configured_servers
      end
    ensure
      ENV["DOCLING_SERVERS"] = previous_configuration
    end

    assert_match(/priorités.*uniques/, error.message)
  end

  test "canonicalise les URL avant de contrôler leur unicité" do
    configuration = JSON.generate([
      { name: "remote-a", url: "http://DOCLING.test:80", priority: 1 },
      { name: "remote-b", url: "http://docling.test/", priority: 2 }
    ])

    error = with_server_configuration(configuration) do
      assert_raises(DoclingServerPool::ConfigurationError) do
        DoclingServerPool.configured_servers
      end
    end

    assert_match(/URL.*uniques/, error.message)
  end

  test "refuse un intervalle d'attente nul ou non fini" do
    [ 0, -1, Float::NAN ].each do |interval|
      assert_raises(DoclingServerPool::ConfigurationError) do
        DoclingServerPool.new(servers: [ REMOTE ], poll_interval: interval)
      end
    end
  end

  test "refuse un port hors de la plage TCP" do
    [ 0, 65_536 ].each do |port|
      configuration = JSON.generate([
        { name: "remote", url: "http://docling.test:#{port}", priority: 1 }
      ])

      with_server_configuration(configuration) do
        assert_raises(DoclingServerPool::ConfigurationError) do
          DoclingServerPool.configured_servers
        end
      end
    end
  end

  private

  def pool(sleeper: ReleasingSleeper.new)
    DoclingServerPool.new(
      servers: [ LOCAL, REMOTE ],
      poll_interval: 0.001,
      sleeper: sleeper
    )
  end

  def waiting_attempt(job_id)
    document(job_id).conversion_attempts.create!(
      status: "queued",
      conversion_options: { "pipeline" => "vlm" },
      execution_job_id: job_id
    )
  end

  def with_server_configuration(configuration)
    previous_configuration = ENV["DOCLING_SERVERS"]
    ENV["DOCLING_SERVERS"] = configuration
    yield
  ensure
    ENV["DOCLING_SERVERS"] = previous_configuration
  end

  def active_attempt(server, job_id)
    document(job_id).conversion_attempts.create!(
      status: "converting",
      conversion_options: { "pipeline" => "vlm" },
      execution_job_id: job_id,
      started_at: Time.current,
      docling_server_name: server.name,
      docling_server_url: server.url,
      docling_server_assigned_at: Time.current
    )
  end

  def document(seed)
    Document.create!(source_sha256: Digest::SHA256.hexdigest(seed))
  end

  def assert_assignment(attempt, server)
    assert_predicate attempt, :converting?
    assert_equal server.name, attempt.docling_server_name
    assert_equal server.url, attempt.docling_server_url
    assert attempt.docling_server_assigned_at
    assert_nil attempt.docling_server_returned_at
  end

  class ReleasingSleeper
    attr_reader :calls

    def initialize(&release)
      @release = release
      @calls = 0
    end

    def sleep(_duration)
      @calls += 1
      @release&.call
    end
  end
end
