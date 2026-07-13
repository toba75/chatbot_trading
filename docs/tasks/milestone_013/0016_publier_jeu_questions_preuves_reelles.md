# T-016 - Publier le jeu annoté réel de questions et preuves attendues

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, exigences d'évaluation M-012 et écarts V1 SP, KA, RA, SD.
- Objectif métier: évaluer le produit sur des questions dont les preuves attendues sont connues dans les PDF réels, sans fabriquer des réponses ou citations de substitution.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `evaluation`, `research_answering`, `knowledge_access` et `source_processing`.
- Objectif métier: relier chaque question d'évaluation à des pages, fragments, assertions et statuts documentaires attendus.
- Langage ubiquitaire: jeu annoté réel, question métier, page attendue, fragment attendu, assertion attendue, statut documentaire, citation ouvrable.
- Invariants critiques: une question n'est exploitable que si ses preuves attendues sont résolubles dans un PDF réel déclaré; une assertion attendue porte un statut documentaire explicite.
- Garde-fous: aucune question cachée dans le code; aucune citation artificielle; aucun succès si une annotation attendue manque; aucun contenu complet de PDF privé imposé en Git.

## Blocages Ou Préconditions

- État GREEN/RED connu: le corpus réel n'est pas encore déclaré; T-015 doit fournir le manifeste strict avant validation complète de cette tâche.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; M-012 fournit le cadre de calibration et de corpus pilote à consommer.
- Décisions manquantes: aucune si le jeu annoté reste un artefact local d'évaluation; créer une ADR si son format devient un contrat durable partagé entre contextes.
- Risques: annotations trop faibles pour détecter une recherche incorrecte; citations non ouvrables; questions de stratégie sans preuve exigée; mélange entre fixtures historiques et corpus réel.

## Tâches

### T-016 - Publier le jeu annoté réel de questions et preuves attendues

- But métier: évaluer le produit sur des questions dont les preuves attendues sont connues.
- Portée DDD: EV, RA, KA, SP, annotations page par page, statuts documentaires et critères de rappel attendu.
- Scénario BDD:
  - Given un corpus réel est déclaré.
  - When un jeu d'évaluation référence ses questions.
  - Then chaque question possède des pages attendues, fragments attendus, assertions attendues et statut documentaire attendu.
- Tests d'acceptation à écrire: `uv run --locked gate`.
- Tests unitaires à écrire: question sans PDF, page hors borne, fragment absent, assertion sans statut, citation non résoluble, question stratégie sans preuve exigée, question sans justification métier, doublon d'identifiant.
- Implémentation attendue: créer un format strict de jeu annoté local, sans contenu PDF complet en Git si les PDF restent privés, et valider que chaque annotation pointe vers le manifeste T-015.
- Invariants et garde-fous: aucune question synthétique cachée dans le code; aucune citation artificielle; aucun succès si une annotation attendue manque; aucun remplacement par corpus fixture.
- Dépendances: T-015, `docs/specs/plan_remediation_m13.md`, `docs/evaluation/m012`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): exiger questions annotees reelles`
- Commit GREEN: `feat(m013): valider jeu annote reel`
