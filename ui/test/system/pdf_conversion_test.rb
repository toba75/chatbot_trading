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
    assert_selector %(canvas[title="Page courante du PDF original"])
    assert_text "Qualification mathématique"
    assert_text(/Verdict : (conformant_within_scope|contradicted|partial|non_verifiable)/)
    assert_link "Rapport de qualification"
    assert_link "Preuve source"
    assert_link "Réponse brute de l’analyseur"

    html_label = find(%(a[role="tab"][aria-selected="true"])).text
    within_frame(find(%(iframe[title="#{html_label} — page 1"]))) do
      assert_selector "img", count: 2
    end

    fill_in "Page", with: "2"
    find_field("Page").send_keys(:enter)
    assert_selector %(iframe[title="#{html_label} — page 2"][src$="#page-2"])

    click_on "Markdown"
    assert_selector %(a[role="tab"][aria-selected="true"]), text: "Markdown"
    within_frame(find(%(iframe[title="Conversion Markdown"]))) do
      assert_text(/While the rules are free/)
    end

    find_link("Markdown").send_keys(:arrow_right)
    assert_selector %(a[role="tab"][aria-selected="true"]), text: "JSON"
    fill_in "Page", with: "2"
    assert_selector %(iframe[title="Projection JSON de la page 2"])
    within_frame(find(%(iframe[title="Projection JSON de la page 2"]))) do
      assert_text(/"kind": "docling_page"/)
      assert_text(/"page_no": 2/)
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
