class ReconcileInterruptedExecutionsJob < ApplicationJob
  STAGING_TIMEOUT = 5.minutes

  queue_as :default

  def perform
    reconcile_staging_conversions
    reconcile_staging_qualifications
    reconcile(ConversionAttempt.converting, "ConvertDocumentJob", :converting?)
    reconcile(MathQualification.running, "QualifyMathJob", :running?)
  end

  private

  def reconcile_staging_conversions
    ConversionAttempt.staging.where(updated_at: ..STAGING_TIMEOUT.ago).find_each do |attempt|
      attempt.with_lock do
        next unless attempt.staging?
        if (job = pending_job_for(attempt, "ConvertDocumentJob"))
          attempt.update!(status: "queued", execution_job_id: job.active_job_id)
          next
        end

        attempt.update!(
          status: "failed",
          error_code: "enqueue_interrupted",
          error_message: "La mise en file de conversion a été interrompue avant la création du job.",
          completed_at: Time.current
        )
      end
    end
  end

  def reconcile_staging_qualifications
    MathQualification.staging.where(updated_at: ..STAGING_TIMEOUT.ago).find_each do |qualification|
      qualification.with_lock do
        next unless qualification.staging?
        if (job = pending_job_for(qualification, "QualifyMathJob"))
          qualification.update!(status: "queued", execution_job_id: job.active_job_id)
          next
        end

        qualification.update!(
          status: "failed",
          error_code: "enqueue_interrupted",
          error_message: "La mise en file de qualification a été interrompue avant la création du job.",
          completed_at: Time.current
        )
      end
    end
  end

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

  def pending_job_for(record, job_class_name)
    jobs = SolidQueue::Job.where(class_name: job_class_name, finished_at: nil)
    job = jobs.find_by(active_job_id: record.execution_job_id) if record.execution_job_id.present?
    return job if job

    global_id_fragment = "/#{record.class.name}/#{record.id}"
    jobs.where("arguments::text LIKE ?", "%#{global_id_fragment}%").order(:id).first
  end
end
