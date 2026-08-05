require "digest"

class Document < ApplicationRecord
  class InvalidPdf < StandardError; end
  class NotRetryable < StandardError; end

  PROCESSING_STATUS_LABELS = {
    "conversion_staging" => "Préparation",
    "conversion_queued" => "En attente",
    "conversion_running" => "Conversion en cours",
    "conversion_failed" => "Échec conversion",
    "qualification_missing" => "Qualification à programmer",
    "qualification_staging" => "Préparation de la qualification",
    "qualification_queued" => "Qualification en attente",
    "qualification_running" => "Qualification en cours",
    "qualification_failed" => "Échec qualification",
    "qualification_obsolete" => "Qualification à mettre à jour",
    "completed" => "Terminé"
  }.freeze
  TRANSIENT_PROCESSING_STATUSES = %w[
    conversion_staging conversion_queued conversion_running qualification_staging qualification_queued qualification_running
  ].freeze

  has_one_attached :source_pdf
  has_many :conversion_attempts, -> { order(:id) }, inverse_of: :document
  belongs_to :retried_from, class_name: "Document", optional: true

  validates :source_sha256, length: { is: 64 }, uniqueness: true

  def current_attempt
    conversion_attempts.last || raise(ActiveRecord::RecordNotFound, "Ce document ne possède aucune tentative.")
  end

  def attempt_history
    documents = []
    document = self
    while document
      documents << document
      document = document.retried_from
    end
    ConversionAttempt.where(document: documents).order(id: :desc)
  end

  def start_conversion!(conversion_options:)
    conversion_attempts.create!(status: "staging", conversion_options: conversion_options)
  end

  def processing_status
    key = processing_status_key
    { key: key, label: PROCESSING_STATUS_LABELS.fetch(key) }
  end

  def processing_status_transient?
    TRANSIENT_PROCESSING_STATUSES.include?(processing_status_key)
  end

  def processing_status_key
    attempt = current_attempt
    return "conversion_staging" if attempt.staging?
    return "conversion_queued" if attempt.queued?
    return "conversion_running" if attempt.converting?
    return "conversion_failed" if attempt.failed?

    qualification_status_key(attempt.current_math_qualification)
  end

  def retry_conversion!(conversion_options:)
    with_lock do
      raise NotRetryable, "Seul un traitement échoué peut être relancé." unless current_attempt.failed?

      start_conversion!(conversion_options: conversion_options)
    end
  end

  def self.create_from_pdf!(upload, source_sha256: nil)
    actual_source_sha256 = source_sha256_for_pdf!(upload)
    if source_sha256 && source_sha256 != actual_source_sha256
      raise InvalidPdf, "L'identité SHA-256 fournie ne correspond pas au PDF."
    end
    source_sha256 = actual_source_sha256

    transaction do
      document = create!(source_sha256: source_sha256)
      document.source_pdf.attach(upload)
      document
    end
  end

  def self.source_sha256_for_pdf!(upload)
    validate_pdf!(upload)
    Digest::SHA256.file(upload.tempfile.path).hexdigest
  end

  def self.validate_pdf!(upload)
    raise InvalidPdf, "Le fichier doit porter l’extension .pdf." unless File.extname(upload.original_filename).casecmp?(".pdf")
    raise InvalidPdf, "Le fichier doit être déclaré comme un PDF." unless upload.content_type == "application/pdf"
    raise InvalidPdf, "Le PDF dépasse la taille maximale autorisée." if upload.tempfile.size > Integer(ENV.fetch("PDF_MAX_BYTES"))

    upload.tempfile.rewind
    signature = upload.tempfile.read(5)
    upload.tempfile.rewind
    raise InvalidPdf, "Le fichier ne possède pas la signature d’un PDF." unless signature == "%PDF-"
  end
  private_class_method :validate_pdf!

  private

  def qualification_status_key(qualification)
    return "qualification_missing" unless qualification
    return "qualification_staging" if qualification.staging?
    return "qualification_queued" if qualification.queued?
    return "qualification_running" if qualification.running?
    return "qualification_failed" if qualification.failed?
    return "qualification_obsolete" unless qualification.current_contract?

    "completed"
  end
end
