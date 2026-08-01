class AllowEmptyMathProgress < ActiveRecord::Migration[8.1]
  def change
    remove_check_constraint :math_qualifications, name: "math_qualifications_total_units"
    add_check_constraint :math_qualifications, "total_units >= 0", name: "math_qualifications_total_units"
  end
end
