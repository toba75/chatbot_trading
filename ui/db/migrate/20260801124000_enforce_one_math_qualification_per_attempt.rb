class EnforceOneMathQualificationPerAttempt < ActiveRecord::Migration[8.1]
  def up
    remove_index :math_qualifications,
      name: "index_math_qualifications_on_attempt_input_and_version"
    remove_index :math_qualifications, :conversion_attempt_id
    add_index :math_qualifications, :conversion_attempt_id, unique: true
  end

  def down
    remove_index :math_qualifications, :conversion_attempt_id
    add_index :math_qualifications, :conversion_attempt_id
    add_index :math_qualifications,
      %i[conversion_attempt_id input_fingerprint analyzer_version],
      unique: true,
      name: "index_math_qualifications_on_attempt_input_and_version"
  end
end
