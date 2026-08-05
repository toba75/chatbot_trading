require "test_helper"

class ReconcileInterruptedExecutionsJobTest < ActiveJob::TestCase
  test "rend terminales les exécutions dont Solid Queue a constaté la perte" do
    attempt = conversion_attempt("conversion-job")
    qualification = math_qualification("qualification-job")
    fail_queue_job("ConvertDocumentJob", attempt.execution_job_id)
    fail_queue_job("QualifyMathJob", qualification.execution_job_id)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_interrupted attempt.reload
    assert_interrupted qualification.reload
  end

  test "rend explicite une mise en file interrompue avant création du job" do
    attempt = staged_conversion_attempt(updated_at: 10.minutes.ago)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate attempt.reload, :failed?
    assert_equal "enqueue_interrupted", attempt.error_code
    assert attempt.completed_at
  end

  test "préserve une conversion en préparation lorsqu'un job existe déjà" do
    attempt = staged_conversion_attempt(updated_at: 10.minutes.ago)
    job = queue_job_for(attempt, "ConvertDocumentJob", "conversion-active-job")

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate attempt.reload, :queued?
    assert_equal job.active_job_id, attempt.execution_job_id
    assert_nil attempt.completed_at
  end

  test "rend explicite une qualification interrompue avant création du job" do
    qualification = staged_math_qualification(updated_at: 10.minutes.ago)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate qualification.reload, :failed?
    assert_equal "enqueue_interrupted", qualification.error_code
    assert qualification.completed_at
  end

  test "préserve une qualification en préparation lorsqu'un job existe déjà" do
    qualification = staged_math_qualification(updated_at: 10.minutes.ago)
    job = queue_job_for(qualification, "QualifyMathJob", "qualification-active-job")

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate qualification.reload, :queued?
    assert_equal job.active_job_id, qualification.execution_job_id
    assert_nil qualification.completed_at
  end

  test "ignore une mise en file en préparation récente" do
    attempt = staged_conversion_attempt(updated_at: 1.minute.ago)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate attempt.reload, :staging?
    assert_nil attempt.completed_at
  end

  test "ignore une exécution encore prise en charge par Solid Queue" do
    attempt = conversion_attempt("active-job")
    queue_job("ConvertDocumentJob", attempt.execution_job_id)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate attempt.reload, :converting?
    assert_nil attempt.completed_at
  end

  test "exige la classe de job attendue avant de terminaliser" do
    attempt = conversion_attempt("wrong-class-job")
    fail_queue_job("QualifyMathJob", attempt.execution_job_id)

    ReconcileInterruptedExecutionsJob.perform_now

    assert_predicate attempt.reload, :converting?
  end

  private

  def conversion_attempt(execution_job_id)
    document = Document.create!(source_sha256: "a" * 64)
    document.conversion_attempts.create!(
      status: "converting",
      conversion_options: { "pipeline" => "vlm" },
      execution_job_id: execution_job_id,
      started_at: Time.current
    )
  end

  def staged_conversion_attempt(updated_at:)
    document = Document.create!(source_sha256: "d" * 64)
    document.conversion_attempts.create!(
      status: "staging",
      conversion_options: { "pipeline" => "vlm" },
      created_at: updated_at,
      updated_at: updated_at
    )
  end

  def staged_math_qualification(updated_at:)
    document = Document.create!(source_sha256: "e" * 64)
    attempt = document.conversion_attempts.create!(
      status: "succeeded",
      conversion_options: { "pipeline" => "vlm" }
    )
    MathQualification.build_for(
      attempt,
      docling_document_sha256: "f" * 64
    ).tap do |qualification|
      qualification.save!
      qualification.update_columns(created_at: updated_at, updated_at: updated_at)
    end
  end

  def math_qualification(execution_job_id)
    document = Document.create!(source_sha256: "b" * 64)
    attempt = document.conversion_attempts.create!(
      status: "succeeded",
      conversion_options: { "pipeline" => "vlm" }
    )
    MathQualification.build_for(
      attempt,
      docling_document_sha256: "c" * 64
    ).tap do |qualification|
      qualification.update!(
        status: "running",
        phase: "source_analysis",
        execution_job_id: execution_job_id,
        started_at: Time.current
      )
    end
  end

  def fail_queue_job(class_name, active_job_id)
    SolidQueue::FailedExecution.create!(
      job: queue_job(class_name, active_job_id),
      error: {
        "exception_class" => "SolidQueue::Processes::ProcessPrunedError",
        "message" => "worker perdu",
        "backtrace" => []
      }
    )
  end

  def queue_job(class_name, active_job_id)
    SolidQueue::Job.create!(
      queue_name: "test",
      class_name: class_name,
      arguments: {},
      priority: 0,
      active_job_id: active_job_id,
      scheduled_at: Time.current
    )
  end

  def queue_job_for(record, class_name, active_job_id)
    SolidQueue::Job.create!(
      queue_name: "test",
      class_name: class_name,
      arguments: { "arguments" => [ record.to_global_id.to_s ] },
      priority: 0,
      active_job_id: active_job_id,
      scheduled_at: Time.current
    )
  end

  def assert_interrupted(record)
    assert_predicate record, :failed?
    assert_equal "interrupted_execution", record.error_code
    assert record.completed_at
  end
end
