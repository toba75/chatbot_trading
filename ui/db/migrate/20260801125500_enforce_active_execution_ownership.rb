class EnforceActiveExecutionOwnership < ActiveRecord::Migration[8.1]
  def up
    change_column :conversion_attempts, :execution_job_id, :string, limit: 64
    change_column :math_qualifications, :execution_job_id, :string, limit: 64
    add_check_constraint :conversion_attempts,
      "status <> 'converting' OR execution_job_id IS NOT NULL",
      name: "conversion_attempts_active_execution"
    add_check_constraint :math_qualifications,
      "status <> 'running' OR execution_job_id IS NOT NULL",
      name: "math_qualifications_active_execution"
  end

  def down
    remove_check_constraint :math_qualifications, name: "math_qualifications_active_execution"
    remove_check_constraint :conversion_attempts, name: "conversion_attempts_active_execution"
    change_column :math_qualifications, :execution_job_id, :string
    change_column :conversion_attempts, :execution_job_id, :string
  end
end
