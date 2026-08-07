require "application_system_test_case"
require "net/http"

class PdfConversionTest < ApplicationSystemTestCase
  test "vérifie l'identité de la cible avant le parcours réel" do
    assert_system_test_environment!
  end

  test "convertit réellement le PDF de référence et rafraîchit l'écran par Cable" do
    assert_system_test_environment!
    reference_pdf = unique_reference_pdf
    filename = reference_pdf.basename.to_s
    visit root_path
    attach_file "Documents PDF", reference_pdf
    click_on "Lancer les conversions"
    click_on filename

    assert_text(/En attente|Conversion en cours/)
    running_elapsed = find(%([data-controller="elapsed-time"])).text
    assert_selector(
      %([data-controller="elapsed-time"]),
      exact_text: next_elapsed_second(running_elapsed),
      wait: 5
    )
    assert_text "1 page semble vide — page 5"
    assert_selector %(canvas[title="Page courante du PDF original"])
    assert_text "Qualification mathématique"
    assert_text(/Verdict sémantique : (conformant_within_scope|contradicted|partial|non_verifiable)/)
    assert_link "Rapport de qualification"
    assert_link "Preuve source"
    assert_link "Réponse brute de l’analyseur"

    completed_elapsed = find(%([data-controller="elapsed-time"])).text
    sleep 1.2
    assert_equal completed_elapsed, find(%([data-controller="elapsed-time"])).text
  end

  private

  def assert_system_test_environment!
    uri = URI.join(Capybara.app_host, system_test_environment_path)
    response = Net::HTTP.start(
      uri.host,
      uri.port,
      use_ssl: uri.scheme == "https",
      open_timeout: 5,
      read_timeout: 5
    ) { |http| http.get(uri.request_uri) }

    assert_equal "200", response.code, "La cible du test système n'est pas en environnement test."
    assert_equal ENV.fetch("SYSTEM_TEST_EXPECTED_IDENTITY"), response.body,
      "L'identité de la cible du test système est incohérente."
  end

  def unique_reference_pdf
    source = File.binread("/reference/ostrading-environment-qualification-5-pages.pdf")
    path = Rails.root.join("tmp", "qualification-#{SecureRandom.hex(8)}.pdf")
    File.binwrite(path, "#{source}\n% system-test #{SecureRandom.uuid}\n")
    path
  end

  def next_elapsed_second(clock)
    hours, minutes, seconds = clock.split(":").map(&:to_i)
    total = (hours * 3600) + (minutes * 60) + seconds + 1
    format("%02d:%02d:%02d", total / 3600, total % 3600 / 60, total % 60)
  end
end
