class IndexUnresolvedDoclingServerAssignments < ActiveRecord::Migration[8.1]
  NAME_INDEX = "index_unreturned_docling_assignments_on_name"
  URL_INDEX = "index_unreturned_docling_assignments_on_url"
  OBSOLETE_INDEX = "index_conversion_attempts_on_status_and_docling_server"

  def up
    remove_index :conversion_attempts, name: OBSOLETE_INDEX, if_exists: true
    add_index :conversion_attempts, :docling_server_name,
      name: NAME_INDEX,
      where: "docling_server_returned_at IS NULL"
    add_index :conversion_attempts, :docling_server_url,
      name: URL_INDEX,
      where: "docling_server_returned_at IS NULL"
  end

  def down
    remove_index :conversion_attempts, name: NAME_INDEX
    remove_index :conversion_attempts, name: URL_INDEX
    add_index :conversion_attempts, [ :status, :docling_server_name ],
      name: OBSOLETE_INDEX
  end
end
