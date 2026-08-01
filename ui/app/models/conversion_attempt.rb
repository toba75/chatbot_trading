require "set"

class ConversionAttempt < ApplicationRecord
  belongs_to :document
  has_one :math_qualification, dependent: :destroy

  enum :status, {
    queued: "queued",
    converting: "converting",
    succeeded: "succeeded",
    failed: "failed"
  }, validate: true

  has_one_attached :docling_response
  has_one_attached :docling_document
  has_one_attached :doctags
  has_one_attached :html
  has_one_attached :markdown

  broadcasts_refreshes_to :document
  broadcasts_refreshes_to ->(_attempt) { "documents" }

  validates :conversion_options, presence: true
  validates :execution_job_id, length: { maximum: 64 }, allow_nil: true
  validates :execution_job_id, presence: true, if: :converting?

  def page_inventory
    content_pages = %w[texts tables pictures].flat_map do |collection|
      docling_content.fetch(collection).flat_map do |item|
        item.fetch("prov").map { |provenance| provenance.fetch("page_no") }
      end
    end.to_set

    docling_content.fetch("pages").values
      .map { |page| page.fetch("page_no") }
      .sort
      .map { |number| { number: number, blank: !content_pages.include?(number) } }
  end

  def picture_pages
    docling_content.fetch("pictures").flat_map do |picture|
      picture.fetch("prov").map { |provenance| provenance.fetch("page_no") }
    end.uniq.sort
  end

  def picture_count
    docling_content.fetch("pictures").size
  end

  private

  def docling_content
    @docling_content ||= JSON.parse(docling_document.download)
  end
end
