class CreateMathQualifications < ActiveRecord::Migration[8.1]
  def change
    create_table :math_qualifications do |t|
      t.references :conversion_attempt, null: false, foreign_key: true
      t.string :status, null: false
      t.string :phase, null: false
      t.integer :completed_units, null: false
      t.integer :total_units, null: false
      t.string :verdict
      t.string :analyzer_version, null: false
      t.string :capability_profile, null: false
      t.string :source_sha256, limit: 64, null: false
      t.string :docling_document_sha256, limit: 64, null: false
      t.string :input_fingerprint, limit: 64, null: false
      t.jsonb :summary
      t.string :error_code
      t.text :error_message
      t.datetime :started_at
      t.datetime :completed_at
      t.timestamps

      t.index %i[conversion_attempt_id input_fingerprint analyzer_version],
        unique: true,
        name: "index_math_qualifications_on_attempt_input_and_version"
      t.check_constraint "completed_units >= 0", name: "math_qualifications_completed_units"
      t.check_constraint "total_units > 0", name: "math_qualifications_total_units"
      t.check_constraint "completed_units <= total_units", name: "math_qualifications_progress"
      t.check_constraint "status IN ('queued', 'running', 'succeeded', 'failed')",
        name: "math_qualifications_status"
    end
  end
end
