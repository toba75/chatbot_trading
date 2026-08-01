require "test_helper"

class QualifyMathJobTest < ActiveJob::TestCase
  test "persiste la progression, les preuves et un verdict contradictoire" do
    qualification = create_qualification
    client = FakeClient.new(successful_result)
    source_before = qualification.conversion_attempt.document.source_pdf.download
    document_before = qualification.conversion_attempt.docling_document.download

    job_with(client).perform(qualification)

    qualification.reload
    assert_predicate qualification, :succeeded?
    assert_predicate qualification, :contradicted?
    assert_equal "persisting_result", qualification.phase
    assert_equal 1, qualification.completed_units
    assert_equal 1, qualification.total_units
    assert_equal 2, qualification.summary.fetch("regions")
    assert_equal 1, qualification.summary.fetch("conformant")
    assert_equal 1, qualification.summary.fetch("contradicted")
    assert_equal 0, qualification.summary.fetch("non_verifiable")
    assert_equal 1, qualification.summary.dig("coverage", "pages_total")
    assert_equal 2, qualification.summary.fetch("region_details").size
    assert_equal [], qualification.summary.fetch("page_exclusions")
    assert_equal successful_result.raw_response.b, qualification.analyzer_response.download
    assert_equal successful_result.report_bytes.b, qualification.report.download
    assert_equal successful_result.evidence.b, qualification.source_evidence.download
    assert qualification.started_at
    assert qualification.completed_at
    assert_equal source_before, qualification.conversion_attempt.document.source_pdf.download
    assert_equal document_before, qualification.conversion_attempt.docling_document.download
  end

  test "conserve les artefacts partiels et rend l'échec visible" do
    qualification = create_qualification
    partial = MathQualificationClient::Result.new(
      raw_response: "flux partiel\n",
      report: nil,
      report_bytes: "",
      evidence: "preuve partielle"
    )
    error = MathQualificationClient::QualificationError.new(
      "analysis_failed",
      "Analyse impossible.",
      result: partial
    )

    assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(error: error)).perform(qualification)
    end

    qualification.reload
    assert_predicate qualification, :failed?
    assert_equal "analysis_failed", qualification.error_code
    assert_equal "Analyse impossible.", qualification.error_message
    assert_equal "flux partiel\n", qualification.analyzer_response.download
    assert_equal "preuve partielle", qualification.source_evidence.download
    assert_not qualification.report.attached?
  end

  test "persiste la panne réelle de la frontière HTTP sans déclasser Docling" do
    skip "Activer avec MATH_AUDIT_FAILURE_LIVE=1" unless ENV["MATH_AUDIT_FAILURE_LIVE"] == "1"
    qualification = create_qualification

    error = assert_raises(MathQualificationClient::QualificationError) do
      QualifyMathJob.new.perform(qualification)
    end

    assert_equal "network_error", error.code
    assert_predicate qualification.reload, :failed?
    assert_equal "network_error", qualification.error_code
    assert_predicate qualification.conversion_attempt.reload, :succeeded?
    assert_not qualification.analyzer_response.attached?
    assert_not qualification.source_evidence.attached?
    assert_not qualification.report.attached?
  end

  test "refuse un rapport qui ne correspond pas aux entrées de la qualification" do
    qualification = create_qualification
    result = successful_result
    result.report.fetch("contract")["source_sha256"] = "f" * 64

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse un total de régions qui contredit le détail du rapport" do
    qualification = create_qualification
    result = successful_result
    result.report.dig("alignment", "evaluation", "overall")["regions"] = 3

    error = assert_raises(MathQualificationClient::QualificationError) do
      job_with(FakeClient.new(result)).perform(qualification)
    end

    assert_equal "invalid_report", error.code
    assert_predicate qualification.reload, :failed?
  end

  test "refuse de rejouer une qualification terminale sans mélanger ses preuves" do
    qualification = create_qualification
    job_with(FakeClient.new(successful_result)).perform(qualification)
    original = qualification.reload.attributes.slice("status", "verdict", "summary")
    artifacts = [
      qualification.analyzer_response.download,
      qualification.source_evidence.download,
      qualification.report.download
    ]

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new(error: RuntimeError.new("ne doit pas être appelé"))).perform(qualification)
    end

    assert_equal original, qualification.reload.attributes.slice("status", "verdict", "summary")
    assert_equal artifacts, [
      qualification.analyzer_response.download,
      qualification.source_evidence.download,
      qualification.report.download
    ]
  end

  test "rend une erreur inattendue terminale et explicite" do
    qualification = create_qualification

    assert_raises(RuntimeError) do
      job_with(FakeClient.new(error: RuntimeError.new("rupture inattendue"))).perform(qualification)
    end

    assert_predicate qualification.reload, :failed?
    assert_equal "unexpected_error", qualification.error_code
    assert_equal "rupture inattendue", qualification.error_message
  end

  test "rend terminale une qualification interrompue redélivrée au même job" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    qualification.update!(
      status: "running",
      phase: "source_analysis",
      execution_job_id: job.job_id,
      started_at: 1.minute.ago
    )

    assert_raises(QualifyMathJob::InterruptedExecution) do
      job.perform(qualification)
    end

    qualification.reload
    assert_predicate qualification, :failed?
    assert_equal "interrupted_execution", qualification.error_code
    assert qualification.completed_at
  end

  test "ne prend pas la place d'un autre job de qualification actif" do
    qualification = create_qualification
    qualification.update!(
      status: "running",
      phase: "source_analysis",
      execution_job_id: "job-actif",
      started_at: 1.minute.ago
    )

    assert_raises(QualifyMathJob::InvalidState) do
      job_with(FakeClient.new(successful_result)).perform(qualification)
    end

    assert_predicate qualification.reload, :running?
    assert_nil qualification.completed_at
  end

  test "une ancienne analyse ne peut pas écraser un état terminal" do
    qualification = create_qualification
    job = job_with(FakeClient.new(successful_result))
    qualification.update!(
      status: "failed",
      execution_job_id: job.job_id,
      error_code: "interrupted_execution",
      completed_at: Time.current
    )

    assert_raises(QualifyMathJob::InvalidState) do
      job.send(
        :persist_progress!,
        qualification,
        { "phase" => "candidate_evaluation", "completed_units" => 1, "total_units" => 1 }
      )
    end

    assert_predicate qualification.reload, :failed?
    assert_equal "interrupted_execution", qualification.error_code
  end

  private

  def job_with(client)
    QualifyMathJob.new.tap do |job|
      job.define_singleton_method(:math_qualification_client) { client }
    end
  end

  def create_qualification
    document = Document.create!(source_sha256: "a" * 64)
    document.source_pdf.attach(
      io: StringIO.new("%PDF-source"),
      filename: "source.pdf",
      content_type: "application/pdf"
    )
    attempt = document.conversion_attempts.create!(
      status: "succeeded",
      conversion_options: { "pipeline" => "vlm" }
    )
    attempt.docling_document.attach(
      io: StringIO.new('{"schema_name":"DoclingDocument"}'),
      filename: "document.json",
      content_type: "application/json"
    )
    MathQualification.build_for(
      attempt,
      docling_document_sha256: Digest::SHA256.hexdigest(attempt.docling_document.download)
    ).tap(&:save!)
  end

  def successful_result
    qualification = MathQualification.last
    report = {
      "contract" => {
        "version" => "1.0",
        "analyzer_version" => MathQualification::ANALYZER_VERSION,
        "capability_profile" => MathQualification::CAPABILITY_PROFILE,
        "source_sha256" => qualification.source_sha256,
        "docling_document_sha256" => qualification.docling_document_sha256
      },
      "coverage" => {
        "pages_total" => 1,
        "pages_traced" => 1,
        "pages_unsupported" => 0,
        "pages_ambiguous" => 0
      },
      "pages" => [ { "page" => 1, "status" => "traced" } ],
      "alignment" => {
        "pdf_source_math_regions" => [
          region("#/texts/0", "conformant_within_scope"),
          region("#/texts/1", "contradicted")
        ],
        "evaluation" => {
          "overall" => {
            "regions" => 2,
            "verdicts" => {
              "conformant_within_scope" => 1,
              "contradicted" => 1,
              "non_verifiable" => 0
            }
          }
        }
      }
    }
    report_bytes = JSON.generate(report)
    MathQualificationClient::Result.new(
      raw_response: "flux complet\n",
      report: report,
      report_bytes: report_bytes,
      evidence: "preuve gzip"
    )
  end

  def region(id, verdict)
    {
      "region_id" => id,
      "page" => 1,
      "bbox" => [ 0, 0, 10, 10 ],
      "verdict" => verdict,
      "semantic_reasons" => []
    }
  end

  class FakeClient
    def initialize(result = nil, error: nil)
      @result = result
      @error = error
    end

    def qualify(**_arguments)
      yield({ "phase" => "source_analysis", "completed_units" => 0, "total_units" => 1 })
      raise @error if @error

      yield({ "phase" => "candidate_evaluation", "completed_units" => 1, "total_units" => 1 })
      @result
    end
  end
end
