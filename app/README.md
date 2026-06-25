# Modules de contextes M-001

Ce répertoire matérialise les frontières du monolithe modulaire décrites par DDD-ADR-001 et par la spécification v4.1, sections 4, 13, 14 et 21.

## Registre canonique

Le registre `context_registry.json` déclare explicitement:

- les sept bounded contexts métier;
- leur module applicatif propriétaire;
- leurs couches `domain`, `application` et `adapters`;
- leurs stockages indicatifs possédés;
- le module technique `platform`, qui n'est pas un bounded context métier.

## Contextes métier

| Code | Module | Responsabilité exclusive v4.1 |
|---|---|---|
| SP | `source_processing` | enregistrer, diagnostiquer, convertir, contrôler et publier les versions documentaires canoniques |
| KA | `knowledge_access` | construire les projections de recherche et retourner des preuves candidates traçables |
| EG | `evidence_governance` | créer, vérifier, relier et versionner les affirmations et leurs preuves |
| RA | `research_answering` | planifier une recherche, assembler les preuves, analyser les contradictions et produire une réponse vérifiée |
| CV | `conversation` | conserver la continuité du dialogue et résoudre les références de suivi |
| SD | `strategy_design` | formaliser et compiler des stratégies candidates attribuées |
| EX | `experimentation` | exécuter des protocoles reproductibles et conserver tous les résultats |

## Hors périmètre T-003

T-003 ne crée aucun agrégat métier, aucune persistance opérationnelle, aucune interface utilisateur et aucun connecteur externe.
