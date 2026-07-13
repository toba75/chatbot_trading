# Runbook conversation V1 M-013

## Statut

- Identifiant: `M013-Runbook-Conversation-1.0`
- Contextes: CV, RA, EG, KA et platform.
- Sources: `docs/specs/m008_conversation_produit.md`, `docs/governance/m013_spark_failure_drill.md` et `docs/governance/m013_v1_gap_decisions.md`
- ADR applicables: ADR-008, ADR-009, ADR-010, DDD-ADR-006, DDD-ADR-010
- ADR: non requise; ce runbook documente les contrats publics de conversation existants.

## Scénario BDD

- Given une conversation locale rattache des réponses vérifiées et des citations ouvrables.
- When l'utilisateur pose une question ou suit une conversation.
- Then l'historique reste non factuel, les citations et statuts publics sont visibles et une panne Spark publie un statut explicite.

## Procédure

- Précondition: l'utilisateur sait que la conversation n'est pas une source factuelle; les faits proviennent des preuves et réponses vérifiées.
- Règle utilisateur: historique non factuel.
- Commande vérifiée:

```console
uv run --locked gate
uv run --locked gate
```

- Résultat attendu: append-only conversation, routage de mode justifié, citations ouvrables, statuts publics et pannes Spark explicites restent conformes.
- Erreur explicite: `LLM_UNAVAILABLE`, `LLM_PARTIAL_OUTPUT` ou `CONFLICTING_EVIDENCE` bloque la publication d'une réponse factuelle complète.
- Preuve à conserver: sortie des validateurs, identifiant de conversation, identifiant de réponse vérifiée et statut public affiché.

## Statuts publics

| Statut public | Sens utilisateur |
|---|---|
| `SUPPORTED` | Réponse supportée par citations directes. |
| `PARTIALLY_SUPPORTED` | Support partiel, limites visibles. |
| `INSUFFICIENT_EVIDENCE` | Preuves insuffisantes, abstention attendue. |
| `CONFLICTING_EVIDENCE` | Contradiction visible, pas de synthèse affirmative implicite. |
| `LLM_UNAVAILABLE` | Spark indisponible avant génération complète. |

## Garde-fous

- Fallback silencieux: interdit.
- Aucune réponse textuelle inventée quand Spark est indisponible.
- Aucun prompt complet, preuve complète, réponse complète ou secret dans les logs.
- Les écarts RA et KA différés restent visibles dans le guide utilisateur.
