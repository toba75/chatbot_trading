module TerminalMathQualificationAttachmentProtection
  def delete
    ensure_math_qualification_is_mutable
    super
  end

  def destroy
    ensure_math_qualification_is_mutable
    super
  end

  private

  def ensure_math_qualification_is_mutable
    if record_type == "MathQualification" &&
        MathQualification.where(id: record_id, status: %w[succeeded failed]).exists?
      raise ActiveRecord::ReadOnlyRecord, "MathQualification is marked as readonly"
    end
  end
end

ActiveSupport.on_load(:active_storage_attachment) do
  prepend TerminalMathQualificationAttachmentProtection
end
