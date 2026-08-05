# Résultats sur la qualification 51

## Verdict

`pdf-inspector 0.2.6` produit parfois du texte et des éléments positionnés dans
les régions où Docling ne fournit aucun contenu directement corrigeable. Il ne
fournit cependant pas un ancrage Docling démontré et sa transcription des
formules est trop souvent erronée pour devenir une source de correction ou de
preuve.

La piste est donc conservée comme expérience négative utile. Son intégration au
pipeline n'est pas recommandée dans l'état observé.

## Corpus

L'expérience porte sur les 280 cibles mathématiques de la qualification 51 du
document 19 : 205 `formula_insertion` et 75 `formula_replacement`.

| Entrée | SHA-256 |
|---|---|
| PDF | `029ab94dd73cedab2e1c30d4548df5b11771be547f14c43b68f074ebbf6b9510` |
| Rapport d'audit | `18a9a29dd0a423bd45142b96c2e91e98f9382db2731c1f6df63eb05483431e67` |
| Registre des corrections | `5a6a938e0546bd50a71ad52f8ff3ec707e569192cf03fd37629d60b7e66a5498` |

Le rapport brut est conservé dans [`results/q51.json`](results/q51.json).

## Mesures

| Cohorte | Cibles | Texte régional non vide | Contient le texte source | `needs_ocr=true` | Sans recouvrement exact | Sans voisinage à 36 points |
|---|---:|---:|---:|---:|---:|---:|
| `formula_insertion` | 205 | 189 | 140 | 0 | 56 | 11 |
| `formula_replacement` | 75 | 75 | 10 | 0 | 32 | 16 |
| Total | 280 | 264 | 150 | 0 | 88 | 27 |

Le fait de « contenir le texte source » est seulement un signal : les espaces
sont ignorés et du contenu parasite peut entourer la séquence. Ce n'est pas une
validation de la formule.

Les `TextItem` utilisent les coordonnées PDF bas-gauche. L'expérience applique
donc uniquement leur conversion vers l'origine haut-gauche déclarée par le
rapport d'audit. Après cette conversion, 192 cibles sur 280 recouvrent au moins
un élément positionné et 88 n'en recouvrent aucun.

L'élargissement de 36 points retrouve au moins un élément positionné pour 194
des 205 insertions, mais il ne désigne jamais un voisin unique : la médiane est
de 6 éléments candidats et aucune région n'en a exactement un. Une proximité
textuelle existe donc souvent, mais elle ne fournit ni l'identité Docling ni un
ordre d'insertion univoque.

## Contre-exemples

Le drapeau `needs_ocr` reste faux pour les 280 cibles, y compris lorsque la
transcription est manifestement incompatible avec la source prouvée :

| Cible | Source prouvée | `pdf-inspector` |
|---|---|---|
| `pdf-source:10:449` | `wx−b=0,` | `wx ≠ b =0,` |
| `pdf-source:10:840` | `y=sign(wx−b),` | `y = sign(wx ≠ b),` |
| `pdf-source:10:1173` | `f(x)=sign(w∗x−b∗)` | `ú ú` puis `f (x) = sign(w x ≠ b)` |
| `pdf-source:17:1287` | produit indicé | commence par `Ÿn` et transforme `n−1` en `n≠1` |

Ces erreurs montrent que `needs_ocr=false` ne signifie pas que le texte est
juste. Elles touchent précisément les signes et relations mathématiques qui
motivent notre audit.

## Conclusion

Pour les insertions, les 189 régions non vides et les 194 voisinages non vides
confirment que l'outil peut fournir un signal spatial. Mais 65 régions ne
contiennent même pas la séquence source, 56 n'ont aucun recouvrement exact avec
les éléments positionnés et les voisinages contiennent toujours zéro ou
plusieurs éléments. Ce signal ne réduit donc pas les 205 insertions en
corrections prouvables.

Pour les remplacements, seulement 10 régions sur 75 contiennent la séquence
source et les contre-exemples montrent des substitutions silencieuses de
symboles. Cette cohorte invalide l'usage de l'outil comme extracteur
mathématique secondaire.
