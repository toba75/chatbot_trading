# Jeu annoté page par page M-012

## Scénario BDD

- Given un corpus pilote figé.
- When les pages échantillonnées sont annotées par un oracle humain indépendant.
- Then chaque page évaluée porte des attentes complètes et résolubles avant d'être utilisée par un benchmark.

## Contrat publié

Le jeu annoté M-012 est porté par `AnnotationSet` et contrôlé par `AnnotationCompletenessPolicy`.

Chaque `PageAnnotation` référence une page du `PilotCorpus` et déclare:

- l'état attendu;
- la route attendue;
- la transcription de référence quand la page est évaluable;
- les valeurs numériques critiques avec signe, unité, contexte et provenance;
- les cellules de tableau;
- l'ordre de lecture;
- les zones de provenance résolues par `SourceLocator`;
- la version d'annotation et l'auteur humain.

## Garde-fous

- Une page utilisée par benchmark sans annotation complète est refusée.
- Une zone de provenance non résolue est refusée.
- Une valeur numérique critique sans signe, unité ou contexte est refusée.
- Une annotation générée par le système évalué est refusée.
- Une page vide ou rejetée doit être déclarée par état et raison explicite.
- Un conflit entre état attendu et route attendue est refusé.
- Un jeu annoté remplaçant un jeu historique doit déclarer la version historique remplacée.

## ADR

ADR: non requise. T-004 applique les décisions existantes ADR-002 pour les routes documentaires explicites et ADR-010 pour les gates PowerShell.
