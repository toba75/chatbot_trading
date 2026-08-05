class AddStagingMathQualificationStatus < ActiveRecord::Migration[8.1]
  def up
    remove_check_constraint :math_qualifications, name: "math_qualifications_status"
    add_check_constraint :math_qualifications,
      "status IN ('staging', 'queued', 'running', 'succeeded', 'failed')",
      name: "math_qualifications_status"
  end

  def down
    staging_qualification = select_value(<<~SQL.squish)
      SELECT id
      FROM math_qualifications
      WHERE status = 'staging'
      LIMIT 1
    SQL
    raise ActiveRecord::IrreversibleMigration, "Des qualifications sont encore en préparation." if staging_qualification

    remove_check_constraint :math_qualifications, name: "math_qualifications_status"
    add_check_constraint :math_qualifications,
      "status IN ('queued', 'running', 'succeeded', 'failed')",
      name: "math_qualifications_status"
  end
end
