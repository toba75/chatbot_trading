# Système d'ADR

Ce répertoire contient les **Architecture Decision Records** du projet.

Une ADR documente une décision d'architecture qui influence durablement le produit : structure des données, choix d'un composant, règle de sécurité, stratégie de traitement documentaire, protocole d'indexation, usage d'un modèle ou contrainte de déploiement.

## Objectifs

- rendre les décisions explicites ;
- conserver le contexte et les raisons de chaque choix ;
- éviter les changements implicites ou les bascules silencieuses ;
- lier les choix d'architecture à la spécification, au plan d'implémentation et aux tests ;
- faciliter les revues futures lorsque le corpus, les modèles ou les contraintes matérielles évoluent.

## Règle centrale

**Pas de fallback silencieux.**

Si une décision ne s'applique plus, le système ne doit pas basculer implicitement vers un autre comportement. Une nouvelle ADR doit être créée, ou une ADR existante doit être remplacée explicitement par une ADR ultérieure.

## Cycle de vie

Statuts autorisés :

- `Proposée` : décision en discussion, non applicable en production ;
- `Acceptée` : décision applicable ;
- `Remplacée` : décision remplacée par une ADR plus récente ;
- `Dépréciée` : décision encore visible pour historique, mais à ne plus utiliser pour les nouveaux développements ;
- `Rejetée` : option étudiée puis refusée.

Une ADR `Acceptée` ne doit pas être réécrite pour changer la décision. Pour changer une décision, créer une nouvelle ADR avec un champ `Remplace` et mettre à jour l'index.

Les corrections éditoriales mineures sont autorisées si elles ne changent pas la décision, les conséquences ni le statut.

## Nommage

Format :

```text
ADR-NNN-titre-court-en-kebab-case.md
```

Exemples :

```text
ADR-001-artefacts-canoniques.md
ADR-008-llm-principal-servi-par-vllm.md
ADR-009-modele-embeddings-retenu.md
```

Les numéros sont monotones. Un numéro supprimé ou abandonné ne doit pas être réutilisé.

## Quand créer une ADR

Créer une ADR lorsqu'un choix :

- contraint plusieurs milestones ou workstreams ;
- modifie un contrat de données, une API, un format canonique ou une règle de sécurité ;
- introduit ou remplace un composant structurant ;
- choisit un modèle, un moteur d'inférence, un moteur de recherche ou une base persistante ;
- définit une règle de routage documentaire ou de validation ;
- accepte un compromis durable entre qualité, coût, latence, mémoire ou complexité ;
- contredit ou précise une décision de la spécification.

Ne pas créer d'ADR pour une simple tâche d'implémentation locale, un renommage mineur ou une correction sans impact d'architecture.

## Processus

1. Copier `TEMPLATE.md`.
2. Choisir le prochain numéro disponible dans `index.md`.
3. Renseigner le contexte, la décision, les options considérées et les conséquences.
4. Mettre le statut à `Proposée` ou `Acceptée`.
5. Ajouter l'entrée dans `index.md`.
6. Lier les tests, modules ou milestones concernés lorsque c'est pertinent.

## Index

L'index canonique des ADR se trouve dans [index.md](index.md).
