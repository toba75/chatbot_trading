# DDD-ADR-007 - Les modèles proposent, le domaine décide

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 16

## Contexte

LLM, VLM, OCR, reranker et modèles NLI sont probabilistes. Leurs sorties peuvent aider, mais ne doivent pas modifier directement un état métier protégé.

## Décision

Les modèles proposent des sorties structurées avec provenance. Le domaine décide au moyen de politiques explicites, d'invariants et de commandes validées.

Une sortie de modèle NE DOIT PAS publier une source, vérifier un claim, supporter une réponse, compiler une stratégie ou enregistrer un résultat sans décision de domaine.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Sortie modèle appliquée directement | Rejetée | Introduit hallucination et états non auditables. |
| Modèles désactivés | Rejetée | Rend extraction et synthèse trop limitées. |
| Modèles comme propositions | Retenue | Garde la valeur des modèles sans leur donner autorité métier. |

## Conséquences

### Positives

- Les transitions métier restent déterminées par le domaine.
- Les erreurs de modèle peuvent être diagnostiquées.

### Négatives ou coûts

- Les sorties structurées et politiques de décision doivent être testées.

### Risques et contrôles

- Risque: fallback vers un autre modèle. Contrôle: configuration explicite et absence de fallback silencieux.

## Impact d'implémentation

- Modules concernés: SP, EG, RA, SD, `platform.llm_gateway`.
- Configuration concernée: modèles, schémas de sortie, timeouts.
- Tests attendus: sorties invalides refusées, transitions métier indépendantes.
- Milestones concernées: M-002, M-006, M-007, M-010.

## Liens de traçabilité

- Spécification: sections 3, 16, 20 et 21.
- Plan d'implémentation: M-002, M-006, M-007.
- Tests d'acceptation: claim et réponse vérifiés par politiques.
- Commits: à renseigner lors de l'implémentation.
