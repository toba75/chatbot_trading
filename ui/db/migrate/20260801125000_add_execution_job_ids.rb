class AddExecutionJobIds < ActiveRecord::Migration[8.1]
  def up
    add_column :conversion_attempts, :execution_job_id, :string
    add_column :math_qualifications, :execution_job_id, :string

    execute <<~SQL.squish
      UPDATE conversion_attempts
      SET status = 'failed',
          error_code = 'interrupted_execution',
          error_message = 'La conversion en cours a été interrompue par le déploiement.',
          completed_at = CURRENT_TIMESTAMP
      WHERE status = 'converting'
    SQL
    execute <<~SQL.squish
      UPDATE math_qualifications
      SET status = 'failed',
          error_code = 'interrupted_execution',
          error_message = 'La qualification en cours a été interrompue par le déploiement.',
          completed_at = CURRENT_TIMESTAMP
      WHERE status = 'running'
    SQL
  end

  def down
    remove_column :math_qualifications, :execution_job_id
    remove_column :conversion_attempts, :execution_job_id
  end
end
