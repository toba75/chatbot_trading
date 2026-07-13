# T-007 - Relier les claims après comparaison de portée

## Milestone
- Nom: M-006 - Claims vérifiables.
- Source: spécification v4.1, relations entre affirmations et typologie des contradictions conditionnelles.
- Objectif métier: représenter support, contradiction, généralisation et dépendance sans déclarer de conflit hors portée comparable.

## Contexte DDD
- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: rendre les relations entre claims auditables et versionnées.
- Langage ubiquitaire: `ClaimRelation`, `ClaimRelationPolicy`, `ScopeCompatibility`, `RelateClaims`, `CONTRADICTS`, `APPARENTLY_CONTRADICTS`, `MORE_GENERAL_THAN`, `DERIVED_FROM`.
- Invariants critiques: une contradiction exige comparaison de portée; deux claims non comparables ne produisent pas une contradiction générale; une relation référence les versions de claims.
- Garde-fous: pas de relation par similarité textuelle seule; pas de contradiction sans univers, horizon, fréquence et métrique comparés; pas de relation modifiée sans version.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-006 attendue GREEN.
- Présence des milestones amont dans master: M-004 et M-005 requis et présents.
- Décisions manquantes: aucune si les types de relation restent ceux de la spécification M-006.
- Risques: transformer une différence de période en contradiction; perdre la version du claim; créer un graphe non auditabe.

## Tâches
### T-007 - Relier les claims après comparaison de portée
- But métier: permettre à EG d'expliquer comment des claims se soutiennent, se limitent ou se contredisent.
- Portée DDD: modèle `ClaimRelation`, politique `ClaimRelationPolicy`, value object `ScopeCompatibility`, commande `RelateClaims` et événement `ClaimRelationRecorded`.
- Scénario BDD:
  - Given deux claims opposés portent sur des horizons différents.
  - When EG évalue leur relation.
  - Then aucune relation `CONTRADICTS` générale n'est créée et la raison de non-comparabilité de portée est enregistrée.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant contradiction comparable, contradiction apparente et généralisation.
- Tests unitaires à écrire: tests de compatibilité de portée, version de claims obligatoire, type de relation non autorisé, relation circulaire interdite si non justifiée et raison absente.
- Implémentation attendue: implémenter `ClaimRelation`, repository de relations, policy de comparaison et handler `RelateClaimsHandler`.
- Invariants et garde-fous: aucun type de relation par défaut; aucune contradiction sans comparaison; aucune relation vers un claim inexistant ou une version implicite.
- Dépendances: T-006; DDD-ADR-005; DDD-ADR-010.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m006): couvrir relations claims portee`
- Commit GREEN: `feat(m006): relier claims apres comparaison portee`
