# Instructions agent

## Langue

- Travaille en français.
- L'accentuation est obligatoire.

## Fallback

- Pas de fallback.
- Aucun comportement alternatif ne doit être déclenché silencieusement.

## ADR

- Les décisions d'architecture structurantes sont documentées dans `docs/adr/`.
- Toute nouvelle décision structurante doit créer une ADR à partir de `docs/adr/TEMPLATE.md`.
- Une ADR acceptée ne doit pas être modifiée silencieusement pour changer son sens.
- Si une décision change, créer une nouvelle ADR qui remplace explicitement l'ancienne.
- Mettre à jour `docs/adr/index.md` à chaque création, remplacement ou changement de statut d'une ADR.


## Implémentation

L'implémentation doit suivre un processus **Behavior Driven Development (BDD)** et **Test Driven Development (TDD)**.

1. **BDD** : définir un scénario métier au format `Given-When-Then`.

2. **ATDD/BDD** : écrire les tests d’acceptation automatisés.

3. **TDD** : implémenter chaque étape via des tests unitaires.

Le code doit être strict : pas de valeur par défaut, pas de fallback silencieux

## Règle TDD

Workflow obligatoire
vérification test GREEN -> implémentation test RED -> commit -> implémentation tache -> test GREEN -> commit

## Sous agents

Ne pas interrompre un sous agent qui semble inactif avant 60 minutes d'inactivité supposée