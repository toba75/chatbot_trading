# ADR-040 - Adjudication explicite de l’enrichissement ciblé Docling et Granite

**Statut :** Acceptée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** Pour `TARGETED_ENRICHMENT` seulement, les obligations de récupération Gemma d’ADR-035, ADR-036 et ADR-039, ainsi que le plafond unique de concurrence Granite d’ADR-037
**Remplacée par :** Aucune
**Source :** Parcours réel M-004 du document `DOC-7A3001E2DE57C3E0` et spécification unifiée 4.1

## Contexte

La spécification unifiée définit `TARGETED_ENRICHMENT` comme une comparaison
de deux candidats produits pour la même page : Docling standard et
Granite-Docling ciblé, suivie d’une adjudication qui conserve les deux sorties
et sa décision.

Le worker courant traite au contraire cette route comme une route Granite
exclusive. Après un échec Granite autorisé, il appelle Gemma comme pour une
page sans autre autorité textuelle. Le parcours réel du document
`DOC-7A3001E2DE57C3E0` échoue ainsi sur la page 19 avec
`GEMMA_VISION_UNAVAILABLE`, puis `GEMMA_VISION_OUTPUT_TRUNCATED`, alors que
Docling standard 2.111.0 extrait réellement cette page en 1 386 items et
4 923 caractères, dont sa table mensuelle.

Cette divergence masque un candidat valide, détourne Gemma vers une page déjà
lisible et empêche la publication du document complet.

Le premier parcours corrigé a ensuite mesuré cinq succès Granite sur vingt
pages, soit 75 % d’échecs. Une page échouée sous huit processus Granite
concurrents réussit seule en 60,5 secondes avec 12 items. Deux autres pages
échouées réussissent simultanément en 95 à 97 secondes, avec 9 et 7 items. Le
modèle est donc opérationnel ; le plafond pagewise de huit surcharge ses
instances isolées et fabrique des indisponibilités.

## Décision

- Pour `TARGETED_ENRICHMENT`, le worker **DOIT** exécuter Docling standard et
  Granite-Docling ciblé sur la même page et avec des références candidates
  distinctes.
- Docling standard **DOIT** produire un candidat valide avant toute
  adjudication. Son échec reste terminal ; aucun autre outil ne le remplace.
- Si Granite réussit, l’adjudication **DOIT** retenir Granite comme autorité
  enrichie de la page.
- Si Granite termine avec `DOCLING_PROVENANCE_MISSING` ou
  `GRANITE_DOCLING_UNAVAILABLE`, l’adjudication **DOIT** retenir explicitement
  le candidat Docling standard déjà produit. Ce choix est une décision
  d’autorité tracée, pas un fallback silencieux.
- Tout autre échec Granite **DOIT** rester terminal.
- La trace d’adjudication **DOIT** publier la version de politique, l’outil
  retenu, le hash et la référence du candidat Docling, le hash et la référence
  du candidat Granite lorsqu’il existe, le code d’échec Granite lorsqu’il
  n’existe pas, et une justification non vide.
- Le résultat canonique **DOIT** conserver cette trace structurée. La sortie
  concurrente ne doit jamais être fusionnée silencieusement avec l’autorité
  retenue.
- Gemma **NE DOIT PAS** être appelée pour `TARGETED_ENRICHMENT`. La récupération
  Granite vers Gemma reste réservée aux routes où aucun candidat Docling
  standard n’est contractuellement produit.
- La progression publique compte la page comme terminée seulement après
  l’adjudication complète ; elle ne compte pas séparément les deux candidats.
- `services.workers.concurrency` **DOIT** rester le plafond pagewise explicite,
  fixé à huit pour le runtime local courant.
- `services.workers.granite_concurrency` **DOIT** borner séparément toutes les
  tentatives Granite d’un même worker, routes ciblées et autres routes
  confondues. Sa valeur explicite courante est deux et elle **NE DOIT PAS**
  dépasser le plafond pagewise.
- Toutes les routes **DOIVENT** partager le même limiteur Granite en mémoire ;
  créer un limiteur par page ou par route est interdit.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Continuer Granite puis Gemma | Rejetée | Ignore le candidat Docling prévu par la spécification et échoue sur une page native dense déjà lisible. |
| Dérouter la page vers `NATIVE_STANDARD` | Rejetée | Efface le besoin d’enrichissement et modifie silencieusement le plan M-003. |
| Docling + Granite puis adjudication explicite | Retenue | Applique la spécification unifiée, conserve les preuves concurrentes et borne les issues. |
| Fusionner les textes Docling et Granite | Rejetée | Crée deux autorités concurrentes et une provenance ambiguë. |
| Huit processus Granite simultanés | Rejetée | Le parcours réel produit 75 % d’échecs alors que les mêmes pages réussissent seules ou par deux. |
| Deux processus Granite, huit pages orchestrées | Retenue | Deux pages précédemment échouées réussissent simultanément sans supprimer le parallélisme Docling. |

## Conséquences

### Positives

- Une page complexe mais native reste publiable si l’enrichissement ciblé est
  indisponible et si son candidat Docling est valide.
- Granite reste réellement exécuté et mesurable sur chaque page ciblée.
- Gemma n’est plus sollicitée pour transcrire une page dont Docling possède
  déjà l’autorité de secours explicite.

### Négatives ou coûts

- Chaque page `TARGETED_ENRICHMENT` exécute deux convertisseurs avant de
  publier une unité de progression.
- Le contrat canonique gagne une trace d’adjudication structurée.
- Les pages en attente de Granite occupent un thread pagewise sans lancer une
  troisième instance du modèle.

### Risques et contrôles

- Risque de masquer une panne Granite : seuls deux codes fermés autorisent la
  sélection Docling et le code exact reste dans la trace.
- Risque de sortie ambiguë : une seule autorité est sélectionnée et les hashes
  candidats sont distincts.
- Risque de régression Gemma : un test prouve qu’aucun appel Gemma n’est émis
  pour cette route.
- Risque de saturation Granite : un test de concurrence prouve que toutes les
  routes partagent la limite de deux, tandis que quatre pages orchestrées
  peuvent rester actives.

## Impact d'implémentation

- Modules concernés : domaine de conversion pagewise, orchestration M-004,
  worker routé, fusion canonique et tests M-004.
- Configuration concernée : `services.workers.granite_concurrency=2`, valeur
  obligatoire, strictement positive et inférieure ou égale à
  `services.workers.concurrency`.
- Tests attendus : succès Granite, indisponibilité Granite avec sélection
  Docling, échec non autorisé terminal, trace canonique et absence d’appel
  Gemma.
- Milestones concernées : M-004 et M-013 réalité produit.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md` et section
  `TARGETED_ENRICHMENT` de la spécification unifiée 4.1.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0011_adjuger_enrichissement_cible.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m004/validate_non_native_document_conversion_unit.py`.
- Commits RED : `50b21a609` pour l’adjudication et `8e7fae70e` pour la
  capacité Granite partagée.
- Commits GREEN : `c3a20a141` pour l’adjudication et `000982d15` pour le
  limiteur Granite et sa configuration stricte.

## Notes

ADR-040 est acceptée après la preuve réelle suivante :

- `DOC-7A3001E2DE57C3E0` est `CANONICAL_ACCEPTED`, avec une progression
  publique `SUCCEEDED 36/36` et 13 traces d’adjudication ciblée ;
- sa projection est `SEARCHABLE`, avec une progression publique
  `SUCCEEDED 248/248` et 247 chunks ;
- le runtime relancé par `uv run ui` charge explicitement huit pages
  orchestrées et une capacité Granite de deux ;
- les pages Granite précédemment échouées réussissent seules ou par deux ;
- les scopes `m004` et `m013_config` sont GREEN ;
- `uv sync --locked` et `uv run --locked gate` sont GREEN, avec 429 nœuds
  exécutés exactement une fois et aucun nœud absent, inattendu ou dupliqué.
