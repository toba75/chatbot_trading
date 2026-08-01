require "digest"
require "stringio"

class ConvertDocumentJob < ApplicationJob
  class EnqueueFailed < StandardError; end
  class InvalidState < StandardError; end
  class InterruptedExecution < StandardError; end

  queue_as :conversions
  self.enqueue_after_transaction_commit = false

  def perform(attempt)
    begin_conversion!(attempt)
    result = attempt.document.source_pdf.open do |file|
      docling_client.convert(
        file: file,
        filename: attempt.document.source_pdf.filename.to_s,
        options: attempt.conversion_options
      )
    end
    persist_result!(attempt, result)
  rescue InvalidState, InterruptedExecution
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
      if attempt.queued?
        attempt.update!(
          status: "converting",
          started_at: Time.current,
          execution_job_id: job_id
        )
      elsif attempt.converting? && attempt.execution_job_id == job_id
        attempt.update!(
          status: "failed",
          error_code: "interrupted_execution",
          error_message: "Le processus de conversion s'est arrêté avant de produire un résultat.",
          completed_at: Time.current
        )
        interrupted = true
      else
        raise InvalidState, "La tentative #{attempt.id} n'est plus en attente."
      end
    end
    return unless interrupted

    raise InterruptedExecution, "La tentative #{attempt.id} interrompue a été rendue terminale."
  end

  def docling_client
    DoclingClient.new
  end

  def persist_result!(attempt, result)
    payload = result.payload
    content = payload.fetch("document")
    document_bytes = JSON.generate(content.fetch("json_content"))

    attempt.with_lock do
      ensure_active!(attempt)
      persist_outputs!(attempt, result)
      attempt.update!(
        status: "succeeded",
        page_count: content.fetch("json_content").fetch("pages").size,
        processing_seconds: payload["processing_time"],
        completed_at: Time.current
      )
      create_and_enqueue_qualification!(
        attempt,
        Digest::SHA256.hexdigest(document_bytes)
      )
    end
  end

  def create_and_enqueue_qualification!(attempt, document_sha256)
    qualification = MathQualification.build_for(
      attempt,
      docling_document_sha256: document_sha256
    )
    qualification.save!
    begin
      MathQualification.transaction(requires_new: true) do
        enqueue_math_qualification(qualification)
      end
    rescue SolidQueue::Job::EnqueueError, EnqueueFailed => error
      qualification.update!(
        status: "failed",
        error_code: "enqueue_failed",
        error_message: error.message.truncate(500),
        completed_at: Time.current
      )
    end
  end

  def enqueue_math_qualification(qualification)
    raise EnqueueFailed, "Solid Queue a refusé le job de qualification." unless QualifyMathJob.perform_later(qualification)
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
    attempt.with_lock do
      return unless active?(attempt)

      persist_outputs!(attempt, error.result) if error.result
      attempt.update!(
        status: "failed",
        error_code: error.code,
        error_message: error.message.truncate(500),
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
