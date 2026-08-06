# Résultats de l'expérience Nougat shadow

## Qualification 51 — document 19

Source : `The Hundred Page Machine Learning BOOK.pdf`, empreinte SHA-256
`029ab94dd73cedab2e1c30d4548df5b11771be547f14c43b68f074ebbf6b9510`.

Le corpus contient les 61 cibles, réparties sur 37 pages, pour lesquelles la
qualification 51 avait réellement appelé Gemma. Nougat a chargé ses poids en
6,30 s et traité les pages en 202,64 s, soit 5,48 s par page en moyenne.

- 9 cibles ont une proposition unique, exactement prouvée et applicable ;
- 50 n'ont aucune formule Nougat exactement conforme à la preuve PDF ;
- 2 restent partielles ou ambiguës.

Parmi les 9 cibles applicables, 3 étaient déjà acceptées par Gemma. Les 6 gains
potentiels supplémentaires sont :

- page 10 : `pdf-source:10:449` ;
- page 17 : `pdf-source:17:1287` ;
- page 74 : `pdf-source:74:508`, `pdf-source:74:682` et
  `pdf-source:74:766` ;
- page 138 : `pdf-source:138:205`.

Ces six propositions passent les mêmes contrôles de jetons, de relations et de
reconstruction que le pipeline de correction. Elles ne sont toutefois pas
appliquées par cette expérience.

## Qualification 91 — document 22

Source : `causal-factor-investing.pdf`, empreinte SHA-256
`cf2215890cdd779fd97f5216d9fc04f68dbdda3bcec720d7a77274d4e2a2638a`.

La qualification actuelle ne comporte que deux cibles ayant appelé Gemma, sur
une seule page. Nougat a traité cette page en 3,92 s après 6,39 s de chargement.
Aucune des deux cibles n'a obtenu de proposition exactement conforme.

## Conclusion

Nougat apporte un signal complémentaire mesurable sur le premier document : six
cibles rejetées par Gemma deviennent prouvables et applicables. Il ne constitue
pas un remplacement de Gemma et son rendement varie selon le document. Dans le
cadre de cet exercice non commercial, la suite justifiée est une intégration
sélective, page par page, derrière le contrôle de preuve existant ; une panne
Nougat devra rester distincte d'un résultat Nougat valide mais sans proposition
exacte.
