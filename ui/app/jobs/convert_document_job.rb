require "digest"
require "stringio"

class ConvertDocumentJob < ApplicationJob
  class EnqueueFailed < StandardError; end
  class InvalidState < StandardError; end
  class InterruptedExecution < StandardError; end

  queue_as :conversions
  self.enqueue_after_transaction_commit = true

  def perform(attempt)
    ensure_document_kept!(attempt)
    server = begin_conversion!(attempt)
    document = document_for_attempt(attempt)
    raise InvalidState, "La tentative appartient à un document supprimé." unless document&.kept?

    result = document.source_pdf.open do |file|
      begin
        docling_client(server.url).convert(
          file: file,
          filename: document.source_pdf.filename.to_s,
          options: attempt.conversion_options
        ).tap { mark_docling_returned!(attempt) }
      rescue DoclingClient::ConversionError => error
        mark_docling_returned!(attempt) if error.result
        raise
      end
    end
    persist_result!(attempt, result)
  rescue InvalidState, InterruptedExecution, DoclingServerPool::InvalidAttempt
    raise
  rescue DoclingClient::ConversionError => error
    persist_failure!(attempt, error)
    raise
  rescue StandardError => error
    persist_failure!(
      attempt,
      DoclingClient::ConversionError.new("unexpected_error", error.message)
    )
    raise
  end

  private

  def begin_conversion!(attempt)
    interrupted = false
    persisted = with_kept_document(attempt) do
      attempt.with_lock do
        if attempt.converting? && attempt.execution_job_id == job_id
          attempt.update!(
            status: "failed",
            error_code: "interrupted_execution",
            error_message: "Le processus de conversion s'est arrêté avant de produire un résultat.",
            completed_at: Time.current
          )
          interrupted = true
        elsif !conversion_ready_for_job?(attempt)
          raise InvalidState, "La tentative #{attempt.id} n'est plus en attente."
        end
        true
      end
    end
    raise InvalidState, "La tentative appartient à un document supprimé." unless persisted
    if interrupted
      raise InterruptedExecution, "La tentative #{attempt.id} interrompue a été rendue terminale."
    end

    docling_server_pool.acquire(attempt, job_id: job_id)
  end

  def docling_client(base_url)
    DoclingClient.new(base_url: base_url)
  end

  def docling_server_pool
    DoclingServerPool.new
  end

  def mark_docling_returned!(attempt)
    persisted = with_kept_document(attempt) do
      attempt.with_lock do
        ensure_active!(attempt)
        attempt.update!(docling_server_returned_at: Time.current)
      end
    end
    raise InvalidState, "La tentative appartient à un document supprimé." unless persisted
  end

  def conversion_ready_for_job?(attempt)
    (attempt.staging? || attempt.queued?) &&
      (attempt.execution_job_id.blank? || attempt.execution_job_id == job_id)
  end

  def ensure_document_kept!(attempt)
    return if document_for_attempt(attempt)&.kept?

    raise InvalidState, "La tentative appartient à un document supprimé."
  end

  def document_for_attempt(attempt)
    return unless attempt

    Document.with_discarded.find_by(id: attempt.document_id)
  end

  def with_kept_document(attempt)
    document = document_for_attempt(attempt)
    return false unless document&.kept?

    document.with_lock do
      return false unless document.kept?

      yield document
    end
  end

  def persist_result!(attempt, result)
    payload = result.payload
    content = payload.fetch("document")
    document_bytes = JSON.generate(content.fetch("json_content"))

    ready = with_kept_document(attempt) { attempt.with_lock { ensure_active!(attempt) } }
    raise InvalidState, "La tentative appartient à un document supprimé." unless ready
    attached_outputs = persist_outputs!(attempt, result)
    qualification = nil

    begin
      persisted = with_kept_document(attempt) do
        attempt.with_lock do
          ensure_active!(attempt)
          attempt.update!(
            status: "succeeded",
            page_count: content.fetch("json_content").fetch("pages").size,
            processing_seconds: payload["processing_time"],
            completed_at: Time.current
          )
          qualification = create_qualification!(
            attempt,
            Digest::SHA256.hexdigest(document_bytes)
          )
        end
      end
    rescue InvalidState
      purge_attachments!(attached_outputs)
      raise
    end
    unless persisted
      purge_attachments!(attached_outputs)
      raise InvalidState, "La tentative appartient à un document supprimé."
    end

    enqueue_math_qualification_or_mark_failed!(qualification)
  end

  def create_qualification!(attempt, document_sha256)
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: document_sha256
    )
    qualification.save!
    qualification
  end

  def enqueue_math_qualification_or_mark_failed!(qualification)
    return unless with_kept_document(qualification.conversion_attempt) { true }

    job = enqueue_math_qualification(qualification)
    mark_math_qualification_enqueued!(qualification, job)
  rescue ActiveJob::EnqueueError, SolidQueue::Job::EnqueueError, EnqueueFailed => error
    mark_math_qualification_enqueue_failure!(qualification, error.message)
  end

  def enqueue_math_qualification(qualification)
    QualifyMathJob.perform_later(qualification).tap do |job|
      raise EnqueueFailed, "Solid Queue a refusé le job de qualification." unless job
    end
  end

  def mark_math_qualification_enqueued!(qualification, job)
    with_kept_document(qualification.conversion_attempt) do
      qualification.with_lock do
        if qualification.staging?
          qualification.update!(status: "queued", execution_job_id: job.job_id)
        elsif qualification.queued? && qualification.execution_job_id.blank?
          qualification.update!(execution_job_id: job.job_id)
        end
      end
    end
  end

  def mark_math_qualification_enqueue_failure!(qualification, message)
    with_kept_document(qualification.conversion_attempt) do
      qualification.with_lock do
        return unless qualification.staging? || qualification.queued?

        qualification.update!(
          status: "failed",
          error_code: "enqueue_failed",
          error_message: message.truncate(500),
          completed_at: Time.current
        )
      end
    end
  end

  def attach(attachment, content, filename, content_type)
    attachment.attach(io: StringIO.new(content), filename: filename, content_type: content_type)
  end

  def persist_outputs!(attempt, result)
    attached_outputs = []
    attach_output!(attempt, attached_outputs, attempt.docling_response, result.raw_body,
      "response.json", "application/json") if result.raw_body
    payload = result.payload
    content = payload["document"] if payload.is_a?(Hash)
    return attached_outputs unless content.is_a?(Hash)

    json = content["json_content"]
    attach_output!(attempt, attached_outputs, attempt.docling_document, JSON.generate(json),
      "document.json", "application/json") if json.is_a?(Hash)
    attach_output!(attempt, attached_outputs, attempt.doctags, content["doctags_content"],
      "document.doctags", "text/plain") if content["doctags_content"].is_a?(String)
    attach_output!(attempt, attached_outputs, attempt.html, content["html_content"],
      "document.html", "text/html") if content["html_content"].is_a?(String)
    attach_output!(attempt, attached_outputs, attempt.markdown, content["md_content"],
      "document.md", "text/markdown") if content["md_content"].is_a?(String)
    attached_outputs
  rescue InvalidState
    purge_attachments!(attached_outputs)
    raise
  end

  def persist_failure!(attempt, error)
    ready = with_kept_document(attempt) { attempt.with_lock { active?(attempt) } }
    return unless ready
    attached_outputs = []
    output_error_message = nil
    if error.result
      begin
        attached_outputs = persist_outputs!(attempt, error.result)
      rescue InvalidState
        raise
      rescue StandardError => output_error
        output_error_message = "Les sorties partielles n'ont pas pu être stockées : #{output_error.message}"
      end
    end

    persisted = with_kept_document(attempt) do
      attempt.with_lock do
        if active?(attempt)
          attempt.update!(
            status: "failed",
            error_code: error.code,
            error_message: [ error.message, output_error_message ].compact.join(" ").truncate(500),
            completed_at: Time.current
          )
          true
        else
          false
        end
      end
    end
    purge_attachments!(attached_outputs) unless persisted
  end

  def attach_output!(attempt, attached_outputs, attachment, content, filename, content_type)
    ensure_document_kept!(attempt)
    attach(attachment, content, filename, content_type)
    attached_outputs << attachment
    ensure_document_kept!(attempt)
  end

  def purge_attachments!(attachments)
    attachments.each { |attachment| attachment.purge if attachment.attached? }
  end

  def ensure_active!(attempt)
    return true if active?(attempt)

    raise InvalidState, "La tentative #{attempt.id} n'appartient plus à cette exécution."
  end

  def active?(attempt)
    attempt.converting? && attempt.execution_job_id == job_id
  end
end
