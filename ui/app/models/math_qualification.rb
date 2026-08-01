require "digest"

class MathQualification < ApplicationRecord
  CONTRACT_VERSION = "1.0"
  ANALYZER_VERSION = "0.4.0"
  CAPABILITY_PROFILE = "pdf-docling-semantic-v1"
  PHASES = %w[queued source_analysis docling_alignment candidate_evaluation persisting_result].freeze

  belongs_to :conversion_attempt

  has_one_attached :analyzer_response
  has_one_attached :source_evidence
  has_one_attached :report

  enum :status, {
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

  after_create_commit :broadcast_qualification
  after_update_commit :broadcast_qualification

  validates :phase, inclusion: { in: PHASES }
  validates :completed_units, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :total_units, numericality: { only_integer: true, greater_than_or_equal_to: 0 }
  validates :source_sha256, :docling_document_sha256, :input_fingerprint,
    format: { with: /\A[0-9a-f]{64}\z/ }
  validates :contract_version, inclusion: { in: [ CONTRACT_VERSION ] }
  validates :conversion_attempt_id, uniqueness: true
  validates :execution_job_id, length: { maximum: 64 }, allow_nil: true
  validates :execution_job_id, presence: true, if: :running?
  validate :completed_units_do_not_exceed_total

  def self.build_for(attempt, docling_document_sha256:)
    source_sha256 = attempt.document.source_sha256
    fingerprint = Digest::SHA256.hexdigest(
      [ source_sha256, docling_document_sha256, CONTRACT_VERSION, ANALYZER_VERSION, CAPABILITY_PROFILE ].join(":")
    )
    attempt.build_math_qualification(
      status: "queued",
      phase: "queued",
      completed_units: 0,
      total_units: 1,
      contract_version: CONTRACT_VERSION,
      analyzer_version: ANALYZER_VERSION,
      capability_profile: CAPABILITY_PROFILE,
      source_sha256: source_sha256,
      docling_document_sha256: docling_document_sha256,
      input_fingerprint: fingerprint
    )
  end

  private

  def broadcast_qualification
    broadcast_replace_later_to(
      conversion_attempt.document,
      target: self,
      partial: "documents/math_qualification",
      locals: { qualification: self }
    )
  end

  def completed_units_do_not_exceed_total
    return if completed_units.nil? || total_units.nil? || completed_units <= total_units

    errors.add(:completed_units, "ne peut pas dépasser le total")
  end
end
