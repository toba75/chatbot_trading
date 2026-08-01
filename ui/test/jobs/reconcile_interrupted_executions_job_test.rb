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

  def assert_interrupted(record)
    assert_predicate record, :failed?
    assert_equal "interrupted_execution", record.error_code
    assert record.completed_at
  end
end
