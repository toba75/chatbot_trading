class AddDoclingServerReturnedAtToConversionAttempts < ActiveRecord::Migration[8.1]
  def change
    add_column :conversion_attempts, :docling_server_returned_at, :datetime
  end
end
