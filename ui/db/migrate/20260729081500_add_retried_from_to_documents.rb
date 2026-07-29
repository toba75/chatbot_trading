class AddRetriedFromToDocuments < ActiveRecord::Migration[8.1]
  def change
    add_reference :documents, :retried_from, foreign_key: { to_table: :documents }
  end
end
