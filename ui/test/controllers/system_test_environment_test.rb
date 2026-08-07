require "test_helper"

class SystemTestEnvironmentTest < ActionDispatch::IntegrationTest
  test "publie exclusivement l'identité de l'environnement de test" do
    get system_test_environment_path

    assert_response :success
    assert_equal ENV.fetch("SYSTEM_TEST_EXPECTED_IDENTITY"), response.body
  end
end
