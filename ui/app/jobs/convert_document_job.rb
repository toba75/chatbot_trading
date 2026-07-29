require "stringio"

class ConvertDocumentJob < ApplicationJob
  queue_as :conversions
  self.enqueue_after_transaction_commit = false

  def perform(attempt)
    attempt.update!(status: "converting", started_at: Time.current)
    result = attempt.document.source_pdf.open do |file|
      docling_client.convert(
        file: file,
        filename: attempt.document.source_pdf.filename.to_s,
        options: attempt.conversion_options
      )
    end
    persist_result!(attempt, result)
  rescue DoclingClient::ConversionError => error
    persist_failure!(attempt, error)
    raise
  end

  private

  def docling_client
    DoclingClient.new
  end

  def persist_result!(attempt, result)
    payload = result.payload
    content = payload.fetch("document")

    attempt.with_lock do
      persist_outputs!(attempt, result)
      attempt.update!(
        status: "succeeded",
        page_count: content.fetch("json_content").fetch("pages").size,
        processing_seconds: payload["processing_time"],
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
    attempt.with_lock do
      persist_outputs!(attempt, error.result) if error.result
      attempt.update!(
        status: "failed",
        error_code: error.code,
        error_message: error.message.truncate(500),
        completed_at: Time.current
      )
    end
  end
end
