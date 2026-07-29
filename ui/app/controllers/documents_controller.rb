class DocumentsController < ApplicationController
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

  def html_preview
    document = Document.find(params[:id])
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.html.attached?

    response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    send_data attempt.html.download, type: "text/html", disposition: "inline"
  end

  private

  def source_pdf
    params.require(:document).require(:source_pdf)
  end
end
