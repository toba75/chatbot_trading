# T-008 - Déclencher l'abstention pour données actuelles absentes

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, principe P-12, invariant RA sur données actuelles et erreur `CURRENT_DATA_REQUIRED`.
- Objectif métier: faire de l'abstention un résultat explicite quand la question dépend de données actuelles non autorisées.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: empêcher l'invention de valeurs de marché, prix récents ou données temps réel absentes du corpus autorisé.
- Langage ubiquitaire: `AbstentionPolicy`, `AnswerFreshnessPolicy`, `AbstentionReason`, `REQUIRES_CURRENT_DATA`, `CURRENT_DATA_REQUIRED`, `KnowledgeGap`.
- Invariants critiques: une absence de données actuelles requises entraîne `REQUIRES_CURRENT_DATA` ou une abstention explicite; aucune valeur de marché n'est inventée.
- Garde-fous: aucun appel externe implicite; aucune date courante supposée comme source; aucune valeur synthétique publiée comme fait.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 terminé; T-004 ou T-007 peuvent enrichir le statut final selon le chemin de réponse.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune pour l'abstention; ADR requise si un connecteur de données de marché actuel devient source autorisée.
- Risques: répondre avec une valeur de marché inventée; masquer la dépendance à une donnée actuelle; transformer une lacune en réponse partiellement supportée.

## Tâches
### T-008 - Déclencher l'abstention pour données actuelles absentes
- But métier: rendre l'absence de données actuelles visible et non ambiguë pour l'utilisateur.
- Portée DDD: politiques `AbstentionPolicy` et `AnswerFreshnessPolicy`, objet-valeur `AbstentionReason`, statut `REQUIRES_CURRENT_DATA`, erreur publique `CURRENT_DATA_REQUIRED` et lacune associée.
- Scénario BDD:
  - Given une question nécessite des prix de marché récents.
  - When aucun accès autorisé à des données actuelles n'est présent dans le mandat.
  - Then RA retourne `REQUIRES_CURRENT_DATA`, enregistre la lacune, et n'invente aucune valeur de marché.
- Tests d'acceptation à écrire: `tests/m007/validate_current_data_abstention_acceptance.ps1`, qui échoue tant qu'une question dépendante de données actuelles peut produire une réponse factuelle sans source autorisée.
- Tests unitaires à écrire: tests pour donnée actuelle requise, source actuelle absente, source actuelle non autorisée, mandat qui interdit l'externe, statut `REQUIRES_CURRENT_DATA`, erreur publique `CURRENT_DATA_REQUIRED` et refus d'une valeur inventée.
- Implémentation attendue: ajouter la politique de fraîcheur RA, la classification de besoin en données actuelles, la raison d'abstention et le mapping vers statut/erreur publique.
- Invariants et garde-fous: aucun fallback vers mémoire interne; aucun appel web implicite; aucun prix ou niveau de marché sans preuve autorisée; aucune conversion de `REQUIRES_CURRENT_DATA` en `INSUFFICIENT_EVIDENCE`.
- Dépendances: T-003; T-002; mandat RA; contrats d'erreur publics.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_current_data_abstention_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_current_data_abstention_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m007): couvrir abstention donnees actuelles`
- Commit GREEN: `feat(m007): declarer abstention donnees actuelles`

