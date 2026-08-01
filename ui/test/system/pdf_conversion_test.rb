require "application_system_test_case"

class PdfConversionTest < ApplicationSystemTestCase
  test "convertit réellement le PDF de référence et rafraîchit l'écran par Cable" do
    visit root_path
    attach_file "Document PDF", "/reference/ostrading-environment-qualification-5-pages.pdf"
    click_on "Lancer la conversion"

    assert_text(/En attente|Conversion en cours/)
    running_elapsed = find(%([data-controller="elapsed-time"])).text
    assert_selector(
      %([data-controller="elapsed-time"]),
      exact_text: next_elapsed_second(running_elapsed),
      wait: 5
    )
    assert_text "5 pages"
    assert_text "Page 5 — vide"
    assert_text "2 images — pages 2 et 3"
    assert_selector %(iframe[title="PDF original"])
    assert_selector "pre", text: /While the rules are free/, visible: :all
    assert_text "Qualification mathématique"
    assert_text(/Verdict : (conformant_within_scope|contradicted|partial|non_verifiable)/)
    assert_link "Rapport de qualification"
    assert_link "Preuve source"
    assert_link "Réponse brute de l’analyseur"

    within_frame(find(%(iframe[title="Conversion HTML"]))) do
      assert_selector "img", count: 2
    end

    completed_elapsed = find(%([data-controller="elapsed-time"])).text
    sleep 1.2
    assert_equal completed_elapsed, find(%([data-controller="elapsed-time"])).text
  end

  private

  def next_elapsed_second(clock)
    hours, minutes, seconds = clock.split(":").map(&:to_i)
    total = (hours * 3600) + (minutes * 60) + seconds + 1
    format("%02d:%02d:%02d", total / 3600, total % 3600 / 60, total % 60)
  end
end
