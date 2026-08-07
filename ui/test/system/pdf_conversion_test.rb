require "application_system_test_case"

class PdfConversionTest < ApplicationSystemTestCase
  test "convertit réellement le PDF de référence et rafraîchit l'écran par Cable" do
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
