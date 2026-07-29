require "digest"

class Document < ApplicationRecord
  class InvalidPdf < StandardError; end
  class NotRetryable < StandardError; end

  has_one_attached :source_pdf
  has_many :conversion_attempts, -> { order(:id) }, inverse_of: :document
  belongs_to :retried_from, class_name: "Document", optional: true

  validates :source_sha256, length: { is: 64 }

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
    conversion_attempts.create!(status: "queued", conversion_options: conversion_options)
  end

  def retry_conversion!(conversion_options:)
    with_lock do
      raise NotRetryable, "Seul un traitement échoué peut être relancé." unless current_attempt.failed?

      start_conversion!(conversion_options: conversion_options)
    end
  end

  def self.create_from_pdf!(upload)
    validate_pdf!(upload)

    transaction do
      document = create!(source_sha256: Digest::SHA256.file(upload.tempfile.path).hexdigest)
      document.source_pdf.attach(upload)
      document
    end
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
end
