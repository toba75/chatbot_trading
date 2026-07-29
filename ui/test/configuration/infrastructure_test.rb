require "test_helper"

class InfrastructureTest < ActiveSupport::TestCase
  class ProbeJob < ApplicationJob
    def perform; end
  end

  test "utilise PostgreSQL, Solid Queue et la base Cable dédiée" do
    assert_equal ENV.fetch("TEST_PRIMARY_DATABASE"), ActiveRecord::Base.connection_db_config.database
    assert_equal :solid_queue, Rails.application.config.active_job.queue_adapter
    assert_equal "solid_cable", ActionCable.server.config.cable.fetch("adapter")
    assert_equal ENV.fetch("TEST_CABLE_DATABASE"), cable_database.database
    assert_equal 0.1.seconds, SolidCable.polling_interval
    assert_equal 86_400.seconds, SolidCable.message_retention

    assert_difference -> { SolidQueue::Job.count }, 1 do
      ProbeJob.perform_later
    end
    adapter = ActionCable::SubscriptionAdapter::SolidCable.new(ActionCable.server)
    assert_difference -> { SolidCable::Message.count }, 1 do
      adapter.broadcast("infrastructure-test", "message")
    end
  end

  private

  def cable_database
    ActiveRecord::Base.configurations.configs_for(env_name: "test", name: "cable")
  end
end
