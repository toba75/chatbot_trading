class CreateDocuments < ActiveRecord::Migration[8.1]
  def change
    create_table :documents do |t|
      t.string :status, null: false
      t.string :source_sha256, limit: 64, null: false
      t.jsonb :conversion_options, null: false
      t.integer :page_count
      t.decimal :processing_seconds, precision: 12, scale: 3
      t.datetime :started_at
      t.datetime :completed_at
      t.string :error_code
      t.text :error_message
      t.timestamps
    end

    add_check_constraint :documents,
      "status IN ('queued', 'converting', 'succeeded', 'failed')",
      name: "documents_status"
    add_index :documents, :source_sha256
  end
end
