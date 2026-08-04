class DocumentsController < ApplicationController
  class EnqueueFailed < StandardError; end

  def index
    retried_document_ids = Document.where.not(retried_from_id: nil).select(:retried_from_id)
    @documents = Document.where.not(id: retried_document_ids)
      .includes(:conversion_attempts, source_pdf_attachment: :blob)
      .order(created_at: :desc, id: :desc)
  end

  def new
  end

  def create
    document = Document.transaction do
      created = Document.create_from_pdf!(source_pdf)
      attempt = created.start_conversion!(conversion_options: DoclingClient.conversion_options)
      ConvertDocumentJob.perform_later(attempt)
      created
    end
    redirect_to document
  rescue Document::InvalidPdf => error
    @upload_error = error.message
    render :new, status: :unprocessable_content
  end

  def show
    @document = Document.find(params[:id])
    @attempt = @document.current_attempt
    @previous_attempts = @document.attempt_history.where.not(id: @attempt.id)
    @math_qualification = @attempt.current_math_qualification
    @previous_math_qualifications = @attempt.math_qualifications
      .where.not(id: @math_qualification&.id)
      .order(id: :desc)
  end

  def retry_conversion
    document = Document.find(params[:id])
    Document.transaction do
      attempt = document.retry_conversion!(conversion_options: DoclingClient.conversion_options)
      ConvertDocumentJob.perform_later(attempt)
    end
    redirect_to document
  rescue Document::NotRetryable
    head :conflict
  end

  def retry_math_qualification
    document = Document.find(params[:id])
    document.current_attempt.retry_math_qualification! do |qualification|
      begin
        job = QualifyMathJob.perform_later(qualification)
        raise EnqueueFailed, "Solid Queue a refusé le job de qualification." unless job
      rescue SolidQueue::Job::EnqueueError, EnqueueFailed => error
        mark_enqueue_failure!(qualification, error.message)
      end
    end
    redirect_to document
  rescue ConversionAttempt::MathQualificationNotRetryable
    head :conflict
  end

  def html_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data attempt.html.download, type: "text/html", disposition: "inline"
  end

  def page_html_preview
    document = Document.find(params[:id])
    qualification = document.current_attempt.current_math_qualification
    return head :conflict unless qualification&.succeeded? && qualification.native_page_html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data qualification.native_page_html.download, type: "text/html", disposition: "inline"
  end

  def derived_html_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    qualification = attempt.current_math_qualification
    return head :conflict unless attempt.succeeded? && qualification&.succeeded? && qualification.derived_html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data qualification.derived_html.download, type: "text/html", disposition: "inline"
  end

  def markdown_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.markdown.attached?

    redirect_to rails_blob_path(attempt.markdown, disposition: "inline")
  end

  def docling_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.docling_document.attached?

    redirect_to rails_blob_path(attempt.docling_document, disposition: "inline")
  end

  def docling_page_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.docling_document.attached?

    page = Integer(params[:page], exception: false)
    return head :unprocessable_content unless page&.positive?

    qualification = attempt.current_math_qualification
    math_links = if qualification&.succeeded?
      qualification.summary.fetch("region_details", []).select do |region|
        region["page"] == page && region.key?("link_status")
      end
    else
      []
    end
    projection = attempt.docling_document.open do |file|
      DoclingPageProjection.call(file, page: page, math_links: math_links)
    end
    set_preview_headers("sandbox; default-src 'none'; form-action 'none'; base-uri 'none'")
    send_data JSON.pretty_generate(projection),
      type: "application/json",
      disposition: "inline",
      filename: "docling-page-#{page}.json"
  rescue DoclingPageProjection::PageNotFound
    head :not_found
  end

  private

  def source_pdf
    params.require(:document).require(:source_pdf)
  end

  def set_preview_headers(content_security_policy)
    response.headers["Content-Security-Policy"] = content_security_policy
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
  end

  def mark_enqueue_failure!(qualification, message = "La qualification n'a pas pu être mise en file.")
    qualification.update!(
      status: "failed",
      error_code: "enqueue_failed",
      error_message: message,
      completed_at: Time.current
    )
  end
end
