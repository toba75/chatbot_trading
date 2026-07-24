# Système d'ADR

Ce répertoire contient les Architecture Decision Records du projet.

Une ADR documente une décision d'architecture qui influence durablement le produit: structure de domaine, contrat publié, format canonique, composant structurant, règle de sécurité, stratégie d'exécution, persistance, observabilité ou politique de test.

## Objectifs

- rendre les décisions explicites;
- conserver le contexte et les raisons de chaque choix;
- éviter les changements implicites et les fallbacks silencieux;
- relier les décisions à la spécification, au plan d'implémentation et aux tests;
- permettre de remplacer une décision sans effacer l'historique.

## Familles d'ADR

Deux familles sont suivies dans le même registre:

- `ADR-NNN`: décisions techniques et d'architecture applicative;
- `DDD-ADR-NNN`: décisions structurantes de modélisation DDD.

Les deux séquences sont indépendantes et monotones. Un numéro supprimé, remplacé ou abandonné ne doit pas être réutilisé.

## Cycle de vie

Statuts autorisés:

- `Proposée`: décision en discussion;
- `Acceptée`: décision applicable;
- `Remplacée`: décision remplacée par une ADR plus récente;
- `Dépréciée`: décision conservée pour historique, mais à ne plus utiliser pour les nouveaux développements;
- `Rejetée`: option étudiée puis refusée.

Une ADR acceptée ne doit pas être réécrite pour changer son sens. Pour changer une décision, créer une nouvelle ADR avec le champ `Remplace`, puis mettre à jour `index.md` et le champ `Remplacée par` de l'ancienne ADR.

## Nommage

Formats:

```text
ADR-NNN-titre-court-en-kebab-case.md
DDD-ADR-NNN-titre-court-en-kebab-case.md
```

Exemples:

```text
ADR-001-artefacts-canoniques.md
ADR-008-llm-principal-servi-par-vllm.md
DDD-ADR-001-monolithe-modulaire.md
```

## Quand créer une ADR

Créer une ADR lorsqu'un choix:

- contraint plusieurs milestones ou workstreams;
- définit ou modifie un contrat intercontexte;
- choisit un format canonique, une base, un moteur, un modèle ou un protocole;
- définit une frontière DDD ou une règle de dépendance durable;
- affecte la sécurité, l'observabilité, la reproductibilité ou la qualité scientifique;
- remplace ou précise une décision acceptée.

Ne pas créer d'ADR pour une correction locale, un renommage mineur ou une tâche sans portée durable.

## Processus

1. Copier `TEMPLATE.md`.
2. Choisir le prochain numéro disponible dans `index.md`.
3. Renseigner le contexte, la décision, les conséquences et les liens de traçabilité.
4. Ajouter l'entrée dans `index.md`.
5. Mettre à jour les tâches, tests ou spécifications concernés.
6. Exécuter les validations ciblées des ADR, documents et comportements touchés.

La gate globale n'est jamais une validation par tâche ou par sous-agent. Elle
appartient à l'orchestrateur du milestone, qui l'exécute une seule fois sur un
état final candidat avec le délai long prévu par le workflow. Un correctif se
diagnostique par validations ciblées avant toute nouvelle clôture globale.

## Index

L'index canonique des ADR se trouve dans [index.md](index.md).
