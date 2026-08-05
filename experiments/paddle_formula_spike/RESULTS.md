# Résultats PP-FormulaNet_plus-L et PP-StructureV3

## Verdict

Sur la cohorte q51 de ce document, `PP-FormulaNet_plus-L` est nettement meilleur
que Gemma pour transcrire les petites régions mathématiques isolées. Ce gain ne
devient toutefois que deux corrections complètes supplémentaires avec
l'application actuelle, car la preuve de reconstruction de la formule entière
reste absente.

`PP-StructureV3` ne résout pas les formules manquantes : il retrouve 10 régions
sur 205, correspondant à seulement 5 formules détectées. Il ne retrouve aucune
des 168 régions situées dans un élément `picture` Docling. La combinaison des
deux outils ne débloque donc pas le pipeline dans son état actuel.

## Environnement réel

- GPU observé pendant l'exécution locale : NVIDIA GeForce RTX 4090 Laptop GPU,
  CUDA confirmé par un calcul Paddle ;
- PaddlePaddle GPU 3.2.1, runtime CUDA 12.9 ;
- PaddleOCR 3.5.0 ;
- `PP-FormulaNet_plus-L` explicite, sans modèle par défaut ni repli CPU ;
- image locale observée pendant l'exécution : `paddle-formula-spike:3.5.0`, digest
  `sha256:64aef5ad971dd805c82f8afdcbb34ca94a73f0203ab489c7c03a3b78ffb8147a`.

Le corpus est celui de la qualification 51 du document 19. Les crops de
remplacement ont été régénérés à 600 dpi sans marge. Le premier crop possède le
même SHA-256 (`f50c93c3…452da3`) que celui envoyé à Gemma pendant q51.

## PP-FormulaNet_plus-L

| Mesure | Gemma q51 | PP-FormulaNet_plus-L |
|---|---:|---:|
| Régions disponibles | 68 tentées | 127 tentées |
| Régions exactement prouvées | 12 | 65 |
| Cibles dont toutes les régions sont exactes | non comparable | 40 / 75 |
| Cibles réellement applicables | 3 / 75 | 5 / 75 |

Sur les 68 régions strictement identiques effectivement envoyées à Gemma,
Paddle en valide exactement 39 contre 12 pour Gemma. Paddle gagne seul sur 29
régions, Gemma seul sur 2, et les deux réussissent sur 10. Le gain régional ne
provient donc pas seulement des 59 régions supplémentaires traitées par Paddle.

Les 70 cibles Paddle non applicables se répartissent ainsi :

- 35 ont au moins une région non exacte ;
- 32 ont des régions exactes mais échouent à reconstruire la formule complète ;
- 3 sont refusées parce que le groupement de texte mathématique reste non prouvé.

Le chargement du modèle a pris 31,35 s et l'inférence des 127 régions 57,01 s,
soit 0,45 s par région en moyenne. Le chiffre d'inférence est global et inclut
le traitement du lot ; il ne prétend pas mesurer chaque région séparément.

La différence entre 65 régions exactes et 5 cibles applicables est le résultat
principal : changer de reconnaisseur visuel ne remplace pas la preuve de la
formule complète.

## PP-StructureV3

Le passage a utilisé les 24 seules pages contenant les insertions, rendues à
300 dpi. Les modules tableaux, cachets, graphiques, orientation et redressement
étaient désactivés. `PP-DocLayout_plus-L`, l'OCR anglais et
`PP-FormulaNet_plus-L` étaient actifs.

| Mesure | Résultat |
|---|---:|
| Régions d'insertion | 205 |
| Petites régions de type inline | 202 |
| Régions rattachées à une image Docling | 168 |
| Régions sans ancre Docling | 37 |
| Détections `formula` PP-StructureV3 | 211 |
| Régions d'insertion couvertes | 10 |
| Formules détectées couvrant ces régions | 5 |
| Régions `picture` couvertes | 0 / 168 |
| Régions sans ancre couvertes | 10 / 37 |
| Autres régions sources couvertes, contrôle spatial | 290 / 395 |

Le contrôle spatial à 290 sur 395 régions autres que les insertions confirme que
les coordonnées ont bien été comparées dans le même repère. Le faible résultat
sur les insertions n'est donc pas une simple erreur d'échelle.

L'examen des pages explique l'échec. Les pages 36 et 83 concentrent à elles
seules 118 insertions dans des figures. PP-StructureV3 classe la figure comme
une image et ne redétecte pas récursivement ses expressions internes. La page 83
contient en plus une figure tournée. À l'inverse, sur la page textuelle 67, une
formule complète est correctement détectée et placée dans l'ordre de lecture.

Le chargement du pipeline a pris 24,07 s et l'analyse des 24 pages 117,18 s,
soit 4,88 s par page en moyenne.

## Interprétation après les deux premières passes

Deux conclusions distinctes doivent être conservées :

1. Sur les crops communs de la cohorte q51, `PP-FormulaNet_plus-L` mérite d'être
   conservé comme meilleur générateur de candidats visuels que Gemma. Ce résultat
   sur un document unique ne démontre pas une supériorité générale, et son
   intégration immédiate ne se justifie pas pour seulement deux cibles complètes
   supplémentaires.
2. `PP-StructureV3` sur la page entière n'est pas une solution aux 205
   insertions. L'analyse suivante des images Docling comme sous-documents
   confirme que le blocage principal est la détection dans les diagrammes et la
   reconstruction d'une formule complète prouvée.

Aucune règle de preuve n'a été assouplie et aucun résultat Paddle n'a été accepté
sur la confiance du modèle.

## Éléments picture comme sous-documents

Les neuf `picture` rattachées aux 168 insertions ont été extraites du PDF source
à 300 dpi. Le classifieur d'orientation a identifié les pages 76 et 83 à 270° et
la page 146 à 90°. Les boîtes des preuves ont été transformées dans le même
repère que les prédictions avant leur comparaison.

| Mesure | Sans orientation | Orientation automatique |
|---|---:|---:|
| Pictures analysées | 9 | 9 |
| Régions sources | 168 | 168 |
| Prédictions `formula` | 14 | 17 |
| Régions couvertes | 7 | 16 |
| Régions exactement prouvées isolément | 3 | 3 |
| Inférence | 5,97 s | 8,34 s |

Avec l'orientation automatique, seules deux pictures couvrent des régions
attendues :

- page 83 : trois formules détectées, dont deux couvrent neuf régions sources ;
  aucune n'est prouvable région par région ;
- page 142 : quatorze formules détectées, sept régions couvertes et trois
  exactement prouvées.

Les sept autres pictures ne produisent aucune formule, y compris les diagrammes
mathématiques très lisibles des pages 11, 36, 69 et 76. Le modèle de layout
continue donc à traiter leur contenu comme une figure globale plutôt que comme
des formules internes.

La page 83 expose une seconde limite. Paddle produit des formules complètes,
par exemple une affectation de couche récurrente, tandis que q51 a créé une
cible d'insertion distincte pour chaque fragment PDF (`h`, flèche, indice,
opérateur, etc.). Comparer la formule complète à chaque fragment conduit
légitimement à zéro preuve exacte. Le candidat n'est pas nécessairement faux :
la preuve disponible n'a pas la même granularité.

Cette passe améliore donc la découverte de 0 à 9 régions sur la page 83, mais ne
rend aucune correction supplémentaire applicable. Pour exploiter ce résultat,
il faudrait d'abord grouper géométriquement les glyphes PDF en formules entières,
puis comparer chaque formule Paddle à cette structure source complète. Une
reconnaissance directe de chaque fragment isolé reproduirait la mauvaise
granularité actuelle et ne doit pas être intégrée telle quelle.

## Remplacements locaux et formules inline

Le corpus complémentaire contient les 66 cibles locales rejetées par q51 : 64
par le filtre historique qui assimilait toute suite de deux lettres à de la
prose, et deux après une proposition visuelle non prouvée. Le nouveau contrôle
ne se fonde plus sur cette longueur : il exige que tous les tokens visibles du
charspan Docling soient couverts par la preuve PDF et refuse encore les phrases
non structurées.

| Mesure | Source déterministe | PP-FormulaNet_plus-L |
|---|---:|---:|
| Régions évaluées | 66 | 66 |
| Propositions exactement prouvées | 63 | 36 |
| Corrections réellement applicables | 40 | 25 |

Les 26 refus du chemin déterministe restent explicites : neuf contenus Docling
ne sont pas entièrement couverts par les tokens source, huit contiennent un
connecteur dont le rôle textuel n'est pas prouvé, deux contiennent une phrase
non structurée, quatre ressemblent encore à un mot éclaté, deux utilisent un
symbole non sérialisable et une proposition ne repasse pas la preuve après
sérialisation. FormulaNet est inférieur sur cette cohorte ; il n'est donc pas
intégré au chemin local.

La reconstruction reproductible du HTML avec les 467 corrections q51 et les 40
nouvelles corrections déterministes produit 507 corrections, chacune localisée
une seule fois sur la bonne page. Parmi elles, 504 sont locales. L'audit retrouve
aussi les sept corrections inline de la page 85 sans perte ni duplication.
Le contrôle visuel des pages 10, 36, 41 et 85 confirme le rendu MathML ; il ne
qualifie pas pour autant automatiquement les 152 pages comme parfaites.

Le chargement GPU de FormulaNet a pris 28,24 s et l'inférence des 66 crops
31,42 s. Ces chiffres servent uniquement à comparer les deux générateurs sur
cette cohorte.

## Conclusion

`PP-FormulaNet_plus-L` reste prometteur pour certaines formules de bloc déjà
localisées, mais il n'apporte rien au chemin local : la source PDF déterministe
y produit davantage de corrections applicables. En revanche, PP-StructureV3 ne
détecte presque aucune formule dans les diagrammes, même lorsque chaque
`picture` devient un sous-document et que son orientation est corrigée.

La page 83 montre néanmoins que les rares détections sont des formules complètes
plausibles. Pour exploiter celles-ci, il manque une preuve source de même
granularité : une formule PDF complète au lieu de cibles portant chacune sur un
glyphe ou un petit fragment. Ce regroupement ne résoudrait cependant pas le
verrou dominant de la cohorte : sept pictures, dont la page 36 avec 66 régions,
ne produisent aucune formule à regrouper. Il faudrait donc améliorer séparément
la détection dans les diagrammes.
