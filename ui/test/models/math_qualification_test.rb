require "test_helper"

class MathQualificationTest < ActiveSupport::TestCase
  test "construit une qualification déterministe pour les deux entrées exactes" do
    attempt = conversion_attempt

    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    )

    assert_predicate qualification, :valid?
    assert_predicate qualification, :queued?
    assert_equal "queued", qualification.phase
    assert_equal "2.0", qualification.contract_version
    assert_equal "0.5.25", qualification.analyzer_version
    assert_equal "a" * 64, qualification.source_sha256
    assert_equal "b" * 64, qualification.docling_document_sha256
    assert_equal 64, qualification.input_fingerprint.length
  end

  test "refuse une progression supérieure à son total" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.completed_units = 2

    assert_not_predicate qualification, :valid?
    assert_includes qualification.errors[:completed_units], "ne peut pas dépasser le total"
  end

  test "refuse de créer une qualification avec une identité de contrat incohérente" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.contract_version = "1.0"

    assert_not_predicate qualification, :valid?
    assert_includes qualification.errors[:base], "L’identité du contrat de qualification est incohérente."
  end

  test "fige l’identité du contrat après création" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.save!

    qualification.analyzer_version = "0.5.0"

    assert_not_predicate qualification, :valid?
    assert_includes qualification.errors[:base], "L’identité du contrat de qualification est immuable."
  end

  test "diffuse un changement d’état vers le document" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.save!
    SolidQueue::Job.delete_all

    assert_difference -> { SolidQueue::Job.count }, 1 do
      qualification.update!(
        status: "running",
        phase: "candidate_evaluation",
        completed_units: 0,
        total_units: 0,
        execution_job_id: "job-1"
      )
    end

    job = SolidQueue::Job.last
    assert_equal "Turbo::Streams::ActionBroadcastJob", job.class_name
    assert_includes job.arguments.to_json, '"target":"math_qualification"'
    assert_includes job.arguments.to_json, "documents/current_math_qualification"
  end

  test "diffuse une progression légère par palier de cinq pour cent" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.save!
    qualification.update!(
      status: "running", phase: "source_analysis", completed_units: 0,
      total_units: 100, execution_job_id: "job-1"
    )
    SolidQueue::Job.delete_all
    broadcasts = []
    qualification.define_singleton_method(:broadcast_replace_to) do |*args, **options|
      broadcasts << [ args, options ]
    end

    qualification.update!(completed_units: 1)
    qualification.update!(completed_units: 5)
    qualification.update!(completed_units: 6)

    assert_equal 1, broadcasts.size
    assert_equal "math_qualification_progress", broadcasts.dig(0, 1, :target)
    assert_equal "documents/math_qualification_progress", broadcasts.dig(0, 1, :partial)
    assert_equal 0, SolidQueue::Job.count
  end

  test "un broadcast retardé rend toujours la qualification courante" do
    attempt = conversion_attempt
    historical = MathQualification.build_for(
      attempt,
      docling_document_sha256: "b" * 64
    )
    historical.save!
    historical.update!(
      status: "failed",
      error_code: "historical_failure",
      error_message: "Ancien échec.",
      completed_at: Time.current
    )
    attempt.retry_math_qualification! { |_qualification| }

    html = ApplicationController.render(
      partial: "documents/current_math_qualification",
      locals: { conversion_attempt: attempt }
    )

    assert_includes html, "En attente"
    assert_not_includes html, "Ancien échec."
  end

  test "une qualification terminale et ses preuves sont en lecture seule" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.save!
    stale = MathQualification.find(qualification.id)
    qualification.update!(status: "failed", completed_at: Time.current)

    assert_raises(ActiveRecord::RecordInvalid) do
      stale.update!(error_message: "réécrit")
    end
    assert_raises(ActiveRecord::ReadOnlyRecord) do
      stale.analyzer_response.attach(
        io: StringIO.new("nouvelle preuve"),
        filename: "response.ndjson",
        content_type: "application/x-ndjson"
      )
    end
  end

  test "refuse de purger ou détacher les preuves d’une qualification terminale" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.report.attach(
      io: StringIO.new("rapport"), filename: "report.json", content_type: "application/json"
    )
    qualification.corrections.attach(
      io: StringIO.new("corrections"), filename: "corrections.json", content_type: "application/json"
    )
    qualification.source_evidence.attach(
      io: StringIO.new("preuve"), filename: "evidence.ndjson", content_type: "application/x-ndjson"
    )
    qualification.save!
    qualification.update!(status: "failed", completed_at: Time.current)

    assert_raises(ActiveRecord::ReadOnlyRecord) { qualification.report.purge }
    assert_raises(ActiveRecord::ReadOnlyRecord) { qualification.corrections.detach }
    assert_raises(ActiveRecord::ReadOnlyRecord) { qualification.source_evidence_attachment.destroy! }
    assert_predicate qualification.reload.report, :attached?
    assert_predicate qualification.corrections, :attached?
    assert_predicate qualification.source_evidence, :attached?
  end

  test "refuse un état d'analyse sans propriétaire d'exécution" do
    qualification = MathQualification.build_for(
      conversion_attempt,
      docling_document_sha256: "b" * 64
    )
    qualification.status = "running"

    assert_not_predicate qualification, :valid?
    assert_includes qualification.errors.details[:execution_job_id], { error: :blank }
  end

  private

  def conversion_attempt
    document = Document.create!(source_sha256: "a" * 64)
    document.conversion_attempts.build(
      status: "succeeded",
      conversion_options: { "pipeline" => "vlm" }
    )
  end
end
