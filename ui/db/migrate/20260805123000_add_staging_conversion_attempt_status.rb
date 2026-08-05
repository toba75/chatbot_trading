class AddStagingConversionAttemptStatus < ActiveRecord::Migration[8.1]
  def up
    remove_check_constraint :conversion_attempts, name: "conversion_attempts_status"
    add_check_constraint :conversion_attempts,
      "status IN ('staging', 'queued', 'converting', 'succeeded', 'failed')",
      name: "conversion_attempts_status"
  end

  def down
    staging_attempt = select_value(<<~SQL.squish)
      SELECT id
      FROM conversion_attempts
      WHERE status = 'staging'
      LIMIT 1
    SQL
    raise ActiveRecord::IrreversibleMigration, "Des tentatives sont encore en préparation." if staging_attempt

    remove_check_constraint :conversion_attempts, name: "conversion_attempts_status"
    add_check_constraint :conversion_attempts,
      "status IN ('queued', 'converting', 'succeeded', 'failed')",
      name: "conversion_attempts_status"
  end
end
