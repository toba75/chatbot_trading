require "digest"

class MathQualification < ApplicationRecord
  CONTRACT_VERSION = "2.1"
  ANALYZER_VERSION = "0.8.0"
  CAPABILITY_PROFILE = "pdf-docling-semantic-correction-v3"
  IDENTITY_FIELDS = %w[
    contract_version analyzer_version capability_profile source_sha256
    docling_document_sha256 input_fingerprint
  ].freeze
  PHASES = %w[
    queued source_analysis docling_alignment candidate_evaluation correction_proposal
    correction_export persisting_result
  ].freeze
  PROGRESS_BUCKETS = 20

  belongs_to :conversion_attempt

  has_one_attached :analyzer_response
  has_one_attached :source_evidence
  has_one_attached :report
  has_one_attached :corrections
  has_one_attached :correction_evidence
  has_one_attached :derived_docling_document
  has_one_attached :derived_html
  has_one_attached :derived_markdown
  has_one_attached :native_page_html

  %i[
    analyzer_response source_evidence report corrections correction_evidence
    derived_docling_document derived_html derived_markdown native_page_html
  ].each do |attachment_name|
    define_method("#{attachment_name}=") do |attachable|
      if terminal_status_persisted?
        raise ActiveRecord::ReadOnlyRecord, "MathQualification is marked as readonly"
      end

      super(attachable)
    end
  end

  enum :status, {
    staging: "staging",
    queued: "queued",
    running: "running",
    succeeded: "succeeded",
    failed: "failed"
  }, validate: true

  enum :verdict, {
    conformant_within_scope: "conformant_within_scope",
    contradicted: "contradicted",
    partial: "partial",
    non_verifiable: "non_verifiable"
  }, validate: { allow_nil: true }

  after_create_commit :broadcast_full_qualification, :broadcast_documents_index
  after_update_commit :broadcast_qualification_change

  validates :phase, inclusion: { in: PHASES }
  validates :completed_units, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :total_units, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :source_sha256, :docling_document_sha256, :input_fingerprint,
    format: { with: /\A[0-9a-f]{64}\z/ }
  validates :execution_job_id, length: { maximum: 64 }, allow_nil: true
  validates :execution_job_id, presence: true, if: :running?
  validate :completed_units_do_not_exceed_total
  validate :contract_identity_is_current, on: :create
  validate :contract_identity_is_immutable, on: :update
  validate :terminal_content_is_immutable, on: :update

  def self.build_for(attempt, docling_document_sha256:)
    source_sha256 = attempt.document.source_sha256
    attempt.math_qualifications.build(
      status: "staging",
      phase: "queued",
      completed_units: 0,
      total_units: 1,
      contract_version: CONTRACT_VERSION,
      analyzer_version: ANALYZER_VERSION,
      capability_profile: CAPABILITY_PROFILE,
      source_sha256: source_sha256,
      docling_document_sha256: docling_document_sha256,
      input_fingerprint: fingerprint_for(source_sha256, docling_document_sha256)
    )
  end

  def self.fingerprint_for(source_sha256, docling_document_sha256)
    Digest::SHA256.hexdigest(
      [ source_sha256, docling_document_sha256, CONTRACT_VERSION, ANALYZER_VERSION, CAPABILITY_PROFILE ].join(":")
    )
  end

  def current_contract?
    [ contract_version, analyzer_version, capability_profile, input_fingerprint ] ==
      [
        CONTRACT_VERSION,
        ANALYZER_VERSION,
        CAPABILITY_PROFILE,
        self.class.fingerprint_for(source_sha256, docling_document_sha256)
      ]
  end

  private

  def contract_identity_is_current
    errors.add(:base, "L’identité du contrat de qualification est incohérente.") unless current_contract?
  end

  def contract_identity_is_immutable
    return if (changes_to_save.keys & IDENTITY_FIELDS).empty?

    errors.add(:base, "L’identité du contrat de qualification est immuable.")
  end

  def terminal_status_persisted?
    persisted? && self.class.where(id: id, status: %w[succeeded failed]).exists?
  end

  def terminal_content_is_immutable
    return unless terminal_status_persisted?
    return if changes_to_save.keys.all? { |name| name == "updated_at" }

    errors.add(:base, "Une qualification terminale est en lecture seule.")
  end

  def broadcast_qualification_change
    broadcast_documents_index if previous_changes.key?("status")

    if previous_changes.key?("status") || previous_changes.key?("phase")
      broadcast_full_qualification
    elsif progress_bucket_changed?
      broadcast_progress
    end
  end

  def broadcast_full_qualification
    broadcast_replace_later_to(
      conversion_attempt.document,
      target: "math_qualification",
      partial: "documents/current_math_qualification",
      locals: { conversion_attempt: conversion_attempt }
    )
  end

  def broadcast_documents_index
    broadcast_refresh_later_to("documents")
  end

  def broadcast_progress
    broadcast_replace_to(
      conversion_attempt.document,
      target: "math_qualification_progress",
      partial: "documents/math_qualification_progress",
      locals: { qualification: self }
    )
  end

  def progress_bucket_changed?
    return false unless running?
    return false unless previous_changes.key?("completed_units") || previous_changes.key?("total_units")

    previous_completed = previous_changes.fetch("completed_units", [ completed_units ]).first
    previous_total = previous_changes.fetch("total_units", [ total_units ]).first
    progress_bucket(previous_completed, previous_total) != progress_bucket(completed_units, total_units)
  end

  def progress_bucket(completed, total)
    return 0 unless total.to_i.positive?

    [ completed.to_i * PROGRESS_BUCKETS / total.to_i, PROGRESS_BUCKETS ].min
  end

  def completed_units_do_not_exceed_total
    return if completed_units.nil? || total_units.nil? || completed_units <= total_units

    errors.add(:completed_units, "ne peut pas dépasser le total")
  end
end
