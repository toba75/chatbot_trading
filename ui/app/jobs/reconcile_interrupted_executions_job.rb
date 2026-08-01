class ReconcileInterruptedExecutionsJob < ApplicationJob
  queue_as :default

  def perform
    reconcile(ConversionAttempt.converting, "ConvertDocumentJob", :converting?)
    reconcile(MathQualification.running, "QualifyMathJob", :running?)
  end

  private

  def reconcile(records, job_class_name, active_predicate)
    records.find_each do |record|
      record.with_lock do
        next unless record.public_send(active_predicate)
        next unless failed_execution(record.execution_job_id, job_class_name)

        record.update!(
          status: "failed",
          error_code: "interrupted_execution",
          error_message: "Solid Queue a constaté la perte du processus de traitement.",
          completed_at: Time.current
        )
      end
    end
  end

  def failed_execution(active_job_id, job_class_name)
    SolidQueue::FailedExecution
      .joins(:job)
      .lock
      .find_by(
        solid_queue_jobs: {
          active_job_id: active_job_id,
          class_name: job_class_name
        }
      )
  end
end
