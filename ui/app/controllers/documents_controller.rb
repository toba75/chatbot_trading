class DocumentsController < ApplicationController
  class EnqueueFailed < StandardError; end
  SOURCE_UPLOAD_ERRORS = [ ActiveStorage::IntegrityError, IOError, SystemCallError ].freeze

  def index
    @deleted_view = false
    @documents = listed_documents(Document.kept)
  end

  def trash
    @deleted_view = true
    @documents = listed_documents(Document.with_discarded.discarded)
    render :index
  end

  def new
  end

  def create
    duplicate_uploads = []
    source_upload_failures = []
    attempts = []
    upload_candidates.each do |candidate|
      result = create_document_with_attempt!(candidate)
      if result == :duplicate
        duplicate_uploads << candidate.fetch(:filename)
      elsif result
        attempts << result
      else
        source_upload_failures << candidate.fetch(:filename)
      end
    end

    enqueue_failures = enqueue_conversion_attempts(attempts)
    alert = import_alert(duplicate_uploads, source_upload_failures, enqueue_failures)
    redirect_to documents_path, alert: alert
  rescue Document::InvalidPdf => error
    @upload_error = error.message
    render :new, status: :unprocessable_content
  end

  def show
    @document = kept_document
    @attempt = @document.current_attempt
    @previous_attempts = @document.attempt_history.where.not(id: @attempt.id)
    @math_qualification = @attempt.current_math_qualification
    @previous_math_qualifications = @attempt.math_qualifications
      .where.not(id: @math_qualification&.id)
      .order(id: :desc)
  end

  def retry_conversion
    document = kept_document
    attempt = Document.transaction do
      document.retry_conversion!(conversion_options: DoclingClient.conversion_options)
    end
    enqueue_failure = enqueue_conversion_attempt(attempt)
    redirect_to document, alert: retry_conversion_alert(enqueue_failure)
  rescue Document::NotRetryable
    head :conflict
  end

  def retry_math_qualification
    document = kept_document
    qualification = document.current_attempt.retry_math_qualification! { |_qualification| }
    enqueue_math_qualification_or_mark_failed!(qualification)
    redirect_to document
  rescue ConversionAttempt::MathQualificationNotRetryable
    head :conflict
  end

  def enrich_metadata
    document = kept_document
    metadata = GoogleBooksMetadataEnricher.call(document)
    document.update!(metadata: metadata)
    status = metadata.dig("enrichment", "status")
    redirect_to document, **metadata_enrichment_flash(status)
  end

  def confirm_metadata
    document = kept_document
    volume_id = params.require(:metadata_confirmation).permit(:volume_id).fetch(:volume_id)
    metadata = GoogleBooksMetadataEnricher.confirm(document, volume_id: volume_id)
    document.update!(metadata: metadata)
    redirect_to document, notice: "La correspondance Google Books a été confirmée."
  rescue ActionController::ParameterMissing, GoogleBooksMetadataEnricher::CandidateNotFound
    redirect_to document, alert: "Cette correspondance Google Books n’est plus disponible."
  end

  def reject_metadata
    document = kept_document
    document.update!(metadata: GoogleBooksMetadataEnricher.reject(document))
    redirect_to document, alert: "Aucune correspondance Google Books n’a été retenue."
  rescue GoogleBooksMetadataEnricher::CandidateNotFound
    redirect_to document, alert: "Aucune correspondance Google Books à confirmer ou rejeter n’est disponible."
  end

  def destroy
    document = kept_document
    document.discard!
    redirect_to documents_path, notice: "Le document a été déplacé dans la corbeille."
  end

  def restore
    document = Document.with_discarded.discarded.find(params[:id])
    document.undiscard!
    redirect_to trash_documents_path, notice: "Le document a été restauré."
  end

  def html_preview
    document = kept_document
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data attempt.html.download, type: "text/html", disposition: "inline"
  end

  def page_html_preview
    document = kept_document
    qualification = document.current_attempt.current_math_qualification
    return head :conflict unless qualification&.succeeded? && qualification.native_page_html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data qualification.native_page_html.download, type: "text/html", disposition: "inline"
  end

  def derived_html_preview
    document = kept_document
    attempt = document.current_attempt
    qualification = attempt.current_math_qualification
    return head :conflict unless attempt.succeeded? && qualification&.succeeded? && qualification.derived_html.attached?

    set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'; base-uri 'none'")
    send_data qualification.derived_html.download, type: "text/html", disposition: "inline"
  end

  def markdown_preview
    document = kept_document
    attempt = document.current_attempt
    qualification = attempt.current_math_qualification
    developed = qualification&.succeeded? && qualification.current_contract? &&
      qualification.derived_markdown.attached?
    return head :conflict unless attempt.succeeded? && (developed || attempt.markdown.attached?)

    if developed
      set_preview_headers("sandbox; default-src 'none'; style-src 'unsafe-inline'; form-action 'none'; base-uri 'none'")
      return send_data qualification.derived_markdown.download,
        type: "text/markdown", disposition: "inline"
    end

    redirect_to rails_blob_path(attempt.markdown, disposition: "inline")
  end

  def docling_preview
    document = kept_document
    attempt = document.current_attempt
    return head :conflict unless attempt.succeeded? && attempt.docling_document.attached?

    redirect_to rails_blob_path(attempt.docling_document, disposition: "inline")
  end

  def docling_page_preview
    document = kept_document
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

  def kept_document
    Document.kept.find(params[:id])
  end

  def listed_documents(scope)
    retried_document_ids = Document.kept.where.not(retried_from_id: nil).select(:retried_from_id)
    scope.where.not(id: retried_document_ids)
      .includes(conversion_attempts: :math_qualifications, source_pdf_attachment: :blob)
      .order(created_at: :desc, id: :desc)
  end

  def source_pdfs
    document_params = params.require(:document)
    uploads = if document_params.key?(:source_pdfs)
      document_params.fetch(:source_pdfs)
    else
      document_params.require(:source_pdf)
    end

    Array.wrap(uploads).reject(&:blank?).tap do |selected_uploads|
      raise ActionController::ParameterMissing, :source_pdfs if selected_uploads.empty?
    end
  end

  def upload_candidates
    source_pdfs.map do |upload|
      {
        upload: upload,
        filename: upload_filename(upload),
        source_sha256: Document.source_sha256_for_pdf!(upload)
      }
    rescue Document::InvalidPdf => error
      raise Document::InvalidPdf, "#{upload_filename(upload)} : #{error.message}"
    end
  end

  def create_document_with_attempt!(candidate)
    source_sha256 = candidate.fetch(:source_sha256)
    return :duplicate if Document.with_discarded.exists?(source_sha256: source_sha256)

    document = nil
    attempt = nil
    Document.transaction(requires_new: true) do
      document = Document.create_from_pdf!(candidate.fetch(:upload), source_sha256: source_sha256)
      attempt = document.start_conversion!(conversion_options: DoclingClient.conversion_options)
    end
    attempt

  rescue ActiveRecord::RecordInvalid, ActiveRecord::RecordNotUnique
    raise unless defined?(source_sha256) && Document.with_discarded.exists?(source_sha256: source_sha256)

    :duplicate
  rescue *SOURCE_UPLOAD_ERRORS => error
    raise unless document&.persisted?

    discard_failed_source_upload!(document)
    nil
  end

  def enqueue_conversion_attempts(attempts)
    attempts.filter_map { |attempt| enqueue_conversion_attempt(attempt) }
  end

  def enqueue_conversion_attempt(attempt)
    job = ConvertDocumentJob.perform_later(attempt)
    raise EnqueueFailed, "Solid Queue a refusé le job de conversion." unless job

    mark_conversion_enqueued!(attempt, job)
    nil
  rescue ActiveJob::EnqueueError, SolidQueue::Job::EnqueueError, EnqueueFailed => error
    mark_conversion_enqueue_failure!(attempt, error.message)
    attempt.document.source_pdf.filename.to_s
  end

  def enqueue_math_qualification_or_mark_failed!(qualification)
    job = QualifyMathJob.perform_later(qualification)
    raise EnqueueFailed, "Solid Queue a refusé le job de qualification." unless job
    mark_math_qualification_enqueued!(qualification, job)
  rescue ActiveJob::EnqueueError, SolidQueue::Job::EnqueueError, EnqueueFailed => error
    mark_enqueue_failure!(qualification, error.message)
  end

  def import_alert(duplicate_uploads, source_upload_failures, enqueue_failures)
    messages = []
    messages << duplicate_import_message(duplicate_uploads) if duplicate_uploads.any?
    messages << source_upload_failure_message(source_upload_failures) if source_upload_failures.any?
    messages << conversion_enqueue_failure_message(enqueue_failures) if enqueue_failures.any?
    messages.to_sentence.presence
  end

  def duplicate_import_message(filenames)
    names = filenames.uniq
    if names.one?
      "#{names.first} a déjà été importé."
    else
      "#{names.size} PDF ont déjà été importés : #{names.to_sentence}."
    end
  end

  def conversion_enqueue_failure_message(filenames)
    names = filenames.uniq
    if names.one?
      "#{names.first} n'a pas pu être mis en file de conversion."
    else
      "#{names.size} PDF n'ont pas pu être mis en file de conversion : #{names.to_sentence}."
    end
  end

  def source_upload_failure_message(filenames)
    names = filenames.uniq
    if names.one?
      "#{names.first} n'a pas pu être stocké sur la machine hôte."
    else
      "#{names.size} PDF n'ont pas pu être stockés sur la machine hôte : #{names.to_sentence}."
    end
  end

  def retry_conversion_alert(filename)
    "#{filename} n'a pas pu être remis en file de conversion." if filename
  end

  def upload_filename(upload)
    upload.respond_to?(:original_filename) ? upload.original_filename : "fichier"
  end

  def set_preview_headers(content_security_policy)
    response.headers["Content-Security-Policy"] = content_security_policy
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
  end

  def mark_conversion_enqueue_failure!(attempt, message = "La conversion n'a pas pu être mise en file.")
    mark_conversion_failure!(attempt, "enqueue_failed", message)
  end

  def mark_conversion_enqueued!(attempt, job)
    attempt.with_lock do
      if attempt.staging?
        attempt.update!(status: "queued", execution_job_id: job.job_id)
      elsif attempt.queued? && attempt.execution_job_id.blank?
        attempt.update!(execution_job_id: job.job_id)
      end
    end
  end

  def mark_conversion_failure!(attempt, code, message)
    attempt.with_lock do
      if attempt.staging? || attempt.queued?
        attempt.update!(
          status: "failed",
          error_code: code,
          error_message: message.truncate(500),
          completed_at: Time.current
        )
      end
    end
  end

  def discard_failed_source_upload!(document)
    Document.transaction do
      document.conversion_attempts.destroy_all
      document.destroy!
    end
  end

  def mark_enqueue_failure!(qualification, message = "La qualification n'a pas pu être mise en file.")
    qualification.with_lock do
      if qualification.staging? || qualification.queued?
        qualification.update!(
          status: "failed",
          error_code: "enqueue_failed",
          error_message: message.truncate(500),
          completed_at: Time.current
        )
      end
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

  def metadata_enrichment_flash(status)
    if status == "accepted"
      { notice: "Les métadonnées bibliographiques ont été enrichies depuis Google Books." }
    elsif status == "ambiguous"
      { alert: "Google Books propose des correspondances à vérifier : aucune métadonnée n’a été promue automatiquement." }
    elsif status == "review_required"
      { alert: "Google Books propose une correspondance à confirmer : aucune métadonnée n’a été promue automatiquement." }
    elsif status == "no_match"
      { alert: "Aucune correspondance Google Books suffisamment fiable n’a été trouvée." }
    else
      { alert: "L’enrichissement Google Books a échoué ; le détail est conservé dans les métadonnées." }
    end
  end
end
