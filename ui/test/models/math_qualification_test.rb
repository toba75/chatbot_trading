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
    assert_equal "1.0", qualification.contract_version
    assert_equal "0.4.0", qualification.analyzer_version
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

  test "diffuse chaque changement persistant vers le document" do
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
    assert_equal "Turbo::Streams::ActionBroadcastJob", SolidQueue::Job.last.class_name
    assert_includes SolidQueue::Job.last.arguments.to_json, '"value":"replace"'
    assert_includes SolidQueue::Job.last.arguments.to_json, "math_qualification_#{qualification.id}"
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
