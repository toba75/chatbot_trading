# Plan d’expérience — preuve PDF source + rendu

## Question

La combinaison des instructions internes d’un PDF né numérique et de son rendu
permet-elle de valider automatiquement davantage de symboles critiques qu’une
lecture visuelle seule, sans promouvoir silencieusement une lecture ambiguë ?

Cette expérience porte sur les deux pages de
`source-pages-7-10.pdf`. Elle ne prétend pas qualifier un document entier ni
généraliser son résultat à tous les PDF.

## Entrées figées

- PDF : `../source-pages-7-10.pdf`.
- Candidats existants : Marker `balanced + force_ocr`, Gemma 4 à 200 dpi,
  Gemma 4 à 300 dpi, Gemma 4 avec les deux rendus, Docling/Granite et MinerU.
- Les empreintes SHA-256 de toutes les entrées seront enregistrées dans le
  rapport avant l’évaluation.

## Hypothèses falsifiables

1. Le flux PDF permet de prouver que les indices litigieux de la première page
   sont des `k`, et non des `i`.
2. Le flux PDF permet de prouver que le code litigieux de la seconde page
   dessine un glyphe `/minus`, même si `ToUnicode` déclare `≠`.
3. Un validateur fondé sur ces preuves accepte la lecture conforme et rejette
   systématiquement des mutations contrôlées (`k → i`, `− → ≠`, suppression de
   `C`, suppression de `x`, `−1 → 1`).
4. Une reconnaissance Gemma limitée au bloc, recevant à la fois le crop et les
   faits extraits du PDF, ne dégrade pas les faits déjà corrects et corrige
   l’erreur `k → i` produite par la réconciliation de pages entières.

## Unité et métriques

L’unité primaire est un **fait critique prouvable**, pas une page.

- `taux_preuve_source = faits disposant d’une preuve source / faits ciblés` ;
- `taux_conformité_candidat = faits conformes / faits prouvés` ;
- `taux_rejet_mutations = mutations rejetées / mutations injectées` ;
- `taux_pages_entièrement_prouvées` n’est calculé que si tous les objets
  visibles d’une page ont été couverts, ce qui n’est pas l’objectif de ce POC.

Les faits ciblés sont :

- page 1 : `x_i^(2)`, `x_k^(2)`, l’exemple `x_k`, et la borne `C` ;
- page 2 : les signes moins des trois formules principales, les valeurs `-1`,
  et les relations `≥` / `≤` des contraintes.

## Protocole

1. Extraire les ressources de police, les `Encoding/Differences`, les tables
   `ToUnicode`, les opérations textuelles brutes et les coordonnées de
   caractères.
2. Construire un manifeste qui distingue explicitement :
   - caractère déclaré par `ToUnicode` ;
   - glyphe demandé par l’encodage de police ;
   - caractère observé par l’extracteur de mise en page ;
   - contradiction éventuelle.
3. Évaluer les six candidats existants uniquement sur les faits dont la preuve
   source est établie.
4. Générer des copies mutées des meilleurs candidats et vérifier leur rejet.
5. Recadrer les zones mathématiques litigieuses et les rendre à haute
   résolution. Pour chaque crop, exécuter deux appels Gemma avec le même modèle,
   la même température et la même image :
   - contrôle `image_seule` ;
   - traitement `image_plus_source`, avec le manifeste PDF correspondant.
6. Réévaluer les deux séries avec le même validateur, sans modifier les
   critères après observation des résultats.

## Critères de succès préenregistrés

- 100 % des mutations contrôlées doivent être rejetées.
- Aucun fait contredisant la preuve source ne doit être accepté.
- La sortie ciblée source + crop doit conserver tous les faits déjà corrects,
  corriger `x_k` sur la page 1 et ne pas obtenir un score inférieur au contrôle
  utilisant le même crop sans preuve source.
- Toute preuve absente ou contradictoire doit produire `NON_VÉRIFIABLE`, jamais
  une correction implicite.

## Limites annoncées avant exécution

- La sélection des faits critiques ne couvre pas tout le texte des pages.
- La géométrie PDF ne restitue pas nécessairement l’intention LaTeX originale.
- Un accord de modèles n’est pas une preuve positive.
- Les fontes Type 3, glyphes tracés, images et couches OCR invisibles pourront
  rester non supportés.
- Un résultat positif autorise seulement l’extension graduelle du validateur ;
  il ne qualifie ni Marker ni Gemma sur un document complet.
