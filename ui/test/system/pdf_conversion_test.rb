require "application_system_test_case"

class PdfConversionTest < ApplicationSystemTestCase
  test "convertit réellement le PDF de référence et rafraîchit l'écran par Cable" do
    visit root_path
    attach_file "Document PDF", "/reference/ostrading-environment-qualification-5-pages.pdf"
    click_on "Lancer la conversion"

    assert_text(/En attente|Conversion en cours/)
    running_elapsed = find(%([data-controller="elapsed-time"])).text
    sleep 1.2
    assert_not_equal running_elapsed, find(%([data-controller="elapsed-time"])).text
    assert_text "5 pages"
    assert_text "Page 5 — vide"
    assert_text "2 images — pages 2 et 3"
    assert_selector %(iframe[title="PDF original"])
    assert_selector "pre", text: /While the rules are free/, visible: :all

    within_frame(find(%(iframe[title="Conversion HTML"]))) do
      assert_selector "img", count: 2
    end

    completed_elapsed = find(%([data-controller="elapsed-time"])).text
    sleep 1.2
    assert_equal completed_elapsed, find(%([data-controller="elapsed-time"])).text
  end
end
