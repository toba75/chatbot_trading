class ReconcileInterruptedExecutionsJob < ApplicationJob
  STAGING_TIMEOUT = 5.minutes

  queue_as :default

  def perform
    reconcile_staging_conversions
    reconcile_staging_qualifications
    reconcile(ConversionAttempt, %w[queued converting], "ConvertDocumentJob")
    reconcile(MathQualification, %w[queued running], "QualifyMathJob")
    reconcile_orphaned(ConversionAttempt, "ConvertDocumentJob")
    reconcile_orphaned(MathQualification, "QualifyMathJob")
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

  # Un enregistrement `queued` est réconcilié au même titre qu'une exécution active :
  # si son job a échoué avant de se déclarer en cours, aucun `retry_on` ne le rejouera
  # et la relance de l'interface exige un statut terminal — il resterait « en attente »
  # indéfiniment.
  def reconcile(model, active_statuses, job_class_name)
    model.where(status: active_statuses).find_each do |record|
      record.with_lock do
        next unless active_statuses.include?(record.status)
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

  # Dernier recours pour un enregistrement en file dont Solid Queue ne conserve plus
  # aucune trace : ni exécution en attente, ni échec enregistré. Plus rien ne le
  # reprendra. La condition est volontairement stricte — l'absence totale de ligne de
  # job, et non son seul achèvement — pour qu'un job en cours de finalisation ou en
  # attente d'un worker ne soit jamais confondu avec un orphelin. Le délai de grâce
  # écarte en outre toute course avec la mise en file elle-même.
  def reconcile_orphaned(model, job_class_name)
    model.queued.where(updated_at: ..STAGING_TIMEOUT.ago).find_each do |record|
      record.with_lock do
        next unless record.queued?
        next if queue_job_exists?(record.execution_job_id, job_class_name)

        record.update!(
          status: "failed",
          error_code: "execution_job_missing",
          error_message: "Solid Queue ne conserve plus aucune trace du job de traitement.",
          completed_at: Time.current
        )
      end
    end
  end

  def queue_job_exists?(active_job_id, job_class_name)
    return false if active_job_id.blank?

    SolidQueue::Job.exists?(active_job_id: active_job_id, class_name: job_class_name)
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

    # Le guillemet fermant du GlobalID sérialisé borne la recherche : sans lui,
    # « /MathQualification/42 » désigne aussi les enregistrements 421 ou 4200 et
    # attribue à celui-ci le job d'un autre, qui ne le traitera jamais.
    global_id_fragment = ActiveRecord::Base.sanitize_sql_like(
      "/#{record.class.name}/#{record.id}\""
    )
    jobs.where("arguments::text LIKE ?", "%#{global_id_fragment}%").order(:id).first
  end
end
