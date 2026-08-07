# Couverture du corpus de référence — rapport de l'étape 2 (plan 004)

Ce rapport accompagne `coverage.json` (agrégat rejouable par
`uv run python -m qualification.corpus_reference.coverage aggregate`) et
`coverage-sample.json` (échantillon audité). Il chiffre le gain potentiel des
causes dominantes de non-vérifiabilité, comme l'exige la condition de
complétude de l'étape 2.

## Méthode

Les occurrences brutes par code de refus induisent en erreur : la deuxième
cause en volume (`candidate_content_missing`, 2 356 occurrences) n'apparaît
seule que 4 fois — elle voyage en composés. Le chiffrage repose donc sur une
partition par **famille de levier**, calculée par `lever_partition` et publiée
dans `coverage.json` : une région n'est attribuée à un levier que si sa famille
la bloque seule, car lever une cause ne libère rien tant qu'une autre famille
bloque encore.

Le taux de vraies mathématiques de chaque population est estimé par un
échantillon de 30 régions par strate (graine 20260807), tiré de l'état à
37 livres qualifiés — le 38e, intégré ensuite à l'agrégat, n'en fait pas
partie —, rendu en crops depuis les PDF sources et classé visuellement une à
une. Les coordonnées et la
classe de chaque région examinée sont dans `coverage-sample.json` : l'audit est
rejouable en re-rendant les crops depuis le corpus.

## Partition des régions non conformes (37 livres, 5 021 régions)

| Population | Régions | Part |
|---|---|---|
| Preuve PDF seule (polices, ToUnicode, zones opaques) | 2 525 | 50 % |
| Les deux familles à la fois | 1 306 | 26 % |
| Transcription/liaison Docling seule | 1 003 | 20 % |
| Structure source et mixtes | 187 | 4 % |

## Chiffrage des leviers

**Levier 1 — support des polices (Type1C, CMap ToUnicode, Type0).**
Échantillon : 21/30 mathématiques nettes, 7/30 régions englobantes contenant
des mathématiques mêlées de prose, 2/30 bruits — 93 % des régions contiennent
des mathématiques réelles. **Gain estimé : 1 800 à 2 350 régions rendues
évaluables** (2 525 × 70–93 %). Au niveau page, les mêmes familles maintiennent
3 958 pages en statuts `unsupported` ou `ambiguous`, et 6 277 des 8 616 pages
qualifiées ne sont pas entièrement tracées.
C'est le levier dominant, et la justification quantifiée d'une tranche dédiée.

**Levier 2 — transcription Docling / témoin de corroboration.**
Échantillon : 14/30 vraies mathématiques non transcrites par Docling, 2/30
annotations de figures, 14/30 bruits. **Gain estimé : ≈ 470 régions**, qui
relèvent d'un second transcripteur témoin (voie `experiments/nougat_shadow`),
pas du pipeline de preuve.

**Population mixte (1 306).** 11/30 mathématiques nettes, 3/30 englobantes,
1/30 annotation de figure, 15/30 bruits — dominée par un artefact de concentration (les pages 113-114
d'« Advances in Financial Machine Learning », une matrice numérique imprimée,
produisent des centaines de régions). **≈ 610 régions** supplémentaires,
conditionnées aux deux leviers à la fois.

## Ampleur du bruit du détecteur

Extrapolation des taux de bruit par strate : **≈ 1 300 fausses régions, soit
~26 % des non-évaluées et ~15 % des 8 651 régions totales.** Natures observées :
ornements de chapitres, code source, lettrines, marqueurs et axes de
graphiques, cellules de tableaux, folios romains, une URL. Ce bruit est
hétérogène (plusieurs règles de détection en cause), concentré en clusters, et
ne provient pas majoritairement du scénario « promotion par un seul glyphe »
du finding de la revue d'août — dont deux corrections naïves ont été tentées
puis réfutées, l'une par l'oracle du gate (rappel 0,774 < 1,0), l'autre par
contrôle visuel (48 régions conformes détruites sur le document 22).

## Réserves

- n = 30 par strate : ± 9 à 18 points d'incertitude à 95 %.
- « Évaluable » ≠ « conforme » : une région libérée passe encore par la liaison
  au candidat et l'évaluation sémantique.
- L'échantillon de la population mixte est concentré à 26/30 dans un seul
  ouvrage, fidèlement à la population elle-même.
- Les verdicts agrégés (`coverage.json`) comptent 3 176 régions conformes,
  336 contradictoires, 5 021 non évaluées et 118 manquantes sur 8 651.
- Le 38e livre (`systemic-liquidity-risk-…`) est un échec d'exécution documenté,
  pas une exclusion : « Pipeline VlmPipeline failed » à l'assemblage, après
  conversion complète des 365 pages, reproduit cinq fois sur les deux
  convertisseurs à pile identique. Le constat exact, avec les identifiants de
  jobs, est dans son `outcome` (repris dans `coverage.json`) ; le défaut est à
  instruire côté Docling.
