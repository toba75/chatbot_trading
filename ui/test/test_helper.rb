ENV["RAILS_ENV"] ||= "test"
require_relative "../config/environment"
require "rails/test_help"

module ActiveSupport
  class TestCase
    # Run tests in parallel with specified workers
    parallelize(workers: :number_of_processors)

    # Setup all fixtures in test/fixtures/*.yml for all tests in alphabetical order.
    fixtures :all

    def with_current_math_requalification
      original = ConversionAttempt.instance_method(:current_math_requalification_allowed?)
      ConversionAttempt.define_method(:current_math_requalification_allowed?) { true }
      yield
    ensure
      ConversionAttempt.define_method(:current_math_requalification_allowed?, original)
    end
  end
end
