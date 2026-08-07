require "digest"
require "stringio"

class ConvertDocumentJob < ApplicationJob
  class EnqueueFailed < StandardError; end
  class InvalidState < StandardError; end
  class InterruptedExecution < StandardError; end

  queue_as :conversions
  self.enqueue_after_transaction_commit = true

  def perform(attempt)
    result = attempt.document.source_pdf.open do |file|
      server = begin_conversion!(attempt)
      begin
        docling_client(server.url).convert(
          file: file,
          filename: attempt.document.source_pdf.filename.to_s,
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
    end
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
    attempt.with_lock do
      ensure_active!(attempt)
      attempt.update!(docling_server_returned_at: Time.current)
    end
  end

  def conversion_ready_for_job?(attempt)
    (attempt.staging? || attempt.queued?) &&
      (attempt.execution_job_id.blank? || attempt.execution_job_id == job_id)
  end

  def persist_result!(attempt, result)
    payload = result.payload
    content = payload.fetch("document")
    document_bytes = JSON.generate(content.fetch("json_content"))
    qualification = nil

    attempt.with_lock { ensure_active!(attempt) }
    persist_outputs!(attempt, result)
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
    qualification.with_lock do
      if qualification.staging?
        qualification.update!(status: "queued", execution_job_id: job.job_id)
      elsif qualification.queued? && qualification.execution_job_id.blank?
        qualification.update!(execution_job_id: job.job_id)
      end
    end
  end

  def mark_math_qualification_enqueue_failure!(qualification, message)
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

  def attach(attachment, content, filename, content_type)
    attachment.attach(io: StringIO.new(content), filename: filename, content_type: content_type)
  end

  def persist_outputs!(attempt, result)
    attach(attempt.docling_response, result.raw_body, "response.json", "application/json") if result.raw_body
    payload = result.payload
    content = payload["document"] if payload.is_a?(Hash)
    return unless content.is_a?(Hash)

    json = content["json_content"]
    attach(attempt.docling_document, JSON.generate(json), "document.json", "application/json") if json.is_a?(Hash)
    attach(attempt.doctags, content["doctags_content"], "document.doctags", "text/plain") if content["doctags_content"].is_a?(String)
    attach(attempt.html, content["html_content"], "document.html", "text/html") if content["html_content"].is_a?(String)
    attach(attempt.markdown, content["md_content"], "document.md", "text/markdown") if content["md_content"].is_a?(String)
  end

  def persist_failure!(attempt, error)
    output_error_message = nil
    attempt.with_lock { return unless active?(attempt) }
    if error.result
      begin
        persist_outputs!(attempt, error.result)
      rescue StandardError => output_error
        output_error_message = "Les sorties partielles n'ont pas pu être stockées : #{output_error.message}"
      end
    end

    attempt.with_lock do
      return unless active?(attempt)

      attempt.update!(
        status: "failed",
        error_code: error.code,
        error_message: [ error.message, output_error_message ].compact.join(" ").truncate(500),
        completed_at: Time.current
      )
    end
  end

  def ensure_active!(attempt)
    return if active?(attempt)

    raise InvalidState, "La tentative #{attempt.id} n'appartient plus à cette exécution."
  end

  def active?(attempt)
    attempt.converting? && attempt.execution_job_id == job_id
  end
end
