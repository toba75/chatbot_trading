require "application_system_test_case"

class UiSystemTestCase < ApplicationSystemTestCase
  setup do
    @previous_run_server = Capybara.run_server
    @previous_app_host = Capybara.app_host
    @previous_wait_time = Capybara.default_max_wait_time
    Capybara.run_server = true
    Capybara.app_host = nil
    Capybara.default_max_wait_time = 10
  end

  teardown do
    Capybara.run_server = @previous_run_server
    Capybara.app_host = @previous_app_host
    Capybara.default_max_wait_time = @previous_wait_time
  end
end
