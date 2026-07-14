"""Classification stricte des mises en page numériques visuelles M-004."""

from app.source_processing.adapters.pdf_inspection_worker import (
    _is_dense_visual_numeric_layout,
)


def test_un_graphique_numerique_dense_est_visuel_et_non_natif() -> None:
    # Given une page dont pypdf expose beaucoup d'étiquettes numériques isolées
    #       disposées comme un graphique, sans image XObject.
    fragments = (
        "FIGURE 9-1",
        "First Day Gainers",
        "+ 3 7/8",
        "81 3/4",
        "7 3/4",
        "112 7/8",
        "110 1/4",
        "93 5/8",
        "8 1/8",
        "118",
    )

    # When le signal de disposition est calculé avant le routage documentaire.
    detected = _is_dense_visual_numeric_layout(fragments)

    # Then la page est reconnue comme visuelle et doit quitter NATIVE_STANDARD.
    assert detected is True


def test_un_texte_narratif_avec_un_nombre_reste_natif() -> None:
    # Given une page narrative normale qui contient une référence numérique.
    fragments = (
        "Chapitre 9 : suivre la dynamique du marché.",
        "La stratégie demande une lecture attentive des tendances.",
        "Le graphique 1 illustre seulement l'explication.",
    )

    # When le même signal est calculé.
    detected = _is_dense_visual_numeric_layout(fragments)

    # Then la route native reste possible.
    assert detected is False
