class AddDoclingServerAssignmentToConversionAttempts < ActiveRecord::Migration[8.1]
  def change
    add_column :conversion_attempts, :docling_server_name, :string
    add_column :conversion_attempts, :docling_server_url, :string
    add_column :conversion_attempts, :docling_server_assigned_at, :datetime
  end
end
