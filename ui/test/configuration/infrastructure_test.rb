require "test_helper"
require "erb"
require "yaml"

class InfrastructureTest < ActiveSupport::TestCase
  class ProbeJob < ApplicationJob
    def perform; end
  end

  test "utilise PostgreSQL, Solid Queue et la base Cable dédiée" do
    base_name = Regexp.escape(ENV.fetch("TEST_PRIMARY_DATABASE"))
    assert_match(/\A#{base_name}(?:_\d+)?\z/, ActiveRecord::Base.connection_db_config.database)
    assert_equal :solid_queue, Rails.application.config.active_job.queue_adapter
    assert_equal "solid_cable", ActionCable.server.config.cable.fetch("adapter")
    cable_name = Regexp.escape(ENV.fetch("TEST_CABLE_DATABASE"))
    assert_match(/\A#{cable_name}(?:_\d+)?\z/, cable_database.database)
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

  test "planifie la réconciliation des exécutions interrompues" do
    configuration = YAML.safe_load(
      ERB.new(Rails.root.join("config/recurring.yml").read).result,
      aliases: true
    )
    task = configuration.fetch("test").fetch("reconcile_interrupted_executions")

    assert_equal "ReconcileInterruptedExecutionsJob", task.fetch("class")
    assert_equal "default", task.fetch("queue")
    assert_equal ENV.fetch("INTERRUPTED_EXECUTION_RECONCILIATION_SCHEDULE"), task.fetch("schedule")
  end

  test "autorise les formats Docling non exécutables dans le visualiseur inline" do
    allowed = Rails.application.config.active_storage.content_types_allowed_inline

    assert_includes allowed, "application/json"
    assert_includes allowed, "text/markdown"
  end

  private

  def cable_database
    ActiveRecord::Base.configurations.configs_for(env_name: "test", name: "cable")
  end
end
