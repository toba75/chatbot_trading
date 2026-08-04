class AllowMultipleMathQualificationsPerAttempt < ActiveRecord::Migration[8.1]
  def up
    remove_index :math_qualifications, :conversion_attempt_id
    add_index :math_qualifications, :conversion_attempt_id
  end

  def down
    raise ActiveRecord::IrreversibleMigration,
      "L'historique des qualifications ne peut pas être réduit sans perte de données."
  end
end
