class AddContractVersionToMathQualifications < ActiveRecord::Migration[8.1]
  def up
    add_column :math_qualifications, :contract_version, :string
    execute <<~SQL.squish
      UPDATE math_qualifications
      SET contract_version = '1.0'
      WHERE contract_version IS NULL
    SQL
    change_column_null :math_qualifications, :contract_version, false
  end

  def down
    remove_column :math_qualifications, :contract_version
  end
end
