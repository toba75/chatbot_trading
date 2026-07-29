class ExtractConversionAttempts < ActiveRecord::Migration[8.1]
  OUTPUT_NAMES = %w[docling_response docling_document doctags html markdown].freeze

  def up
    ensure_no_conversion_jobs!

    create_table :conversion_attempts do |t|
      t.references :document, null: false, foreign_key: true
      t.string :status, null: false
      t.jsonb :conversion_options, null: false
      t.integer :page_count
      t.decimal :processing_seconds, precision: 12, scale: 3
      t.datetime :started_at
      t.datetime :completed_at
      t.string :error_code
      t.text :error_message
      t.timestamps
    end
    add_check_constraint :conversion_attempts,
      "status IN ('queued', 'converting', 'succeeded', 'failed')",
      name: "conversion_attempts_status"

    execute <<~SQL
      INSERT INTO conversion_attempts (
        id, document_id, status, conversion_options, page_count,
        processing_seconds, started_at, completed_at, error_code,
        error_message, created_at, updated_at
      )
      SELECT
        id, id, status, conversion_options, page_count,
        processing_seconds, started_at, completed_at, error_code,
        error_message, created_at, updated_at
      FROM documents
    SQL
    execute <<~SQL
      SELECT setval(
        pg_get_serial_sequence('conversion_attempts', 'id'),
        COALESCE(MAX(id), 1),
        MAX(id) IS NOT NULL
      )
      FROM conversion_attempts
    SQL
    execute <<~SQL
      INSERT INTO active_storage_attachments (
        name, record_type, record_id, blob_id, created_at
      )
      SELECT name, 'ConversionAttempt', record_id, blob_id, created_at
      FROM active_storage_attachments
      WHERE record_type = 'Document'
        AND name IN (#{quoted_output_names})
    SQL
    execute <<~SQL
      DELETE FROM active_storage_attachments
      WHERE record_type = 'Document'
        AND name IN (#{quoted_output_names})
    SQL

    remove_columns :documents,
      :status,
      :conversion_options,
      :page_count,
      :processing_seconds,
      :started_at,
      :completed_at,
      :error_code,
      :error_message
  end

  def down
    raise ActiveRecord::IrreversibleMigration, "Les tentatives multiples ne peuvent pas être regroupées sans perte."
  end

  private

  def quoted_output_names
    OUTPUT_NAMES.map { |name| connection.quote(name) }.join(", ")
  end

  def ensure_no_conversion_jobs!
    active_jobs = select_value(<<~SQL).to_i
      SELECT COUNT(*)
      FROM solid_queue_jobs AS jobs
      WHERE jobs.class_name = 'ConvertDocumentJob'
        AND (
          EXISTS (SELECT 1 FROM solid_queue_ready_executions WHERE job_id = jobs.id)
          OR EXISTS (SELECT 1 FROM solid_queue_claimed_executions WHERE job_id = jobs.id)
          OR EXISTS (SELECT 1 FROM solid_queue_scheduled_executions WHERE job_id = jobs.id)
        )
    SQL
    return if active_jobs.zero?

    raise ActiveRecord::MigrationError,
      "La migration exige une file conversions vide et aucun ConvertDocumentJob en cours."
  end
end
