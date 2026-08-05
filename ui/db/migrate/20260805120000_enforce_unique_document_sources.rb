class EnforceUniqueDocumentSources < ActiveRecord::Migration[8.1]
  def up
    duplicate = select_value(<<~SQL.squish)
      SELECT source_sha256
      FROM documents
      GROUP BY source_sha256
      HAVING COUNT(*) > 1
      LIMIT 1
    SQL
    raise ActiveRecord::MigrationError, "documents.source_sha256 contient déjà des doublons." if duplicate

    remove_index :documents, name: "index_documents_on_source_sha256"
    add_index :documents, :source_sha256, unique: true
  end

  def down
    remove_index :documents, name: "index_documents_on_source_sha256"
    add_index :documents, :source_sha256
  end
end
