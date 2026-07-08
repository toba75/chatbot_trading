# Runbook recherche approfondie V1 M-013

## Statut

- Identifiant: `M013-Runbook-DeepResearch-1.0`
- Contextes: RA, EG, KA, SP et EV.
- Sources: `docs/specs/m009_recherche_approfondie_multi_sources.md` et `docs/governance/m013_v1_gap_decisions.md`
- ADR applicables: ADR-005, ADR-008, ADR-010, DDD-ADR-007, DDD-ADR-010
- ADR: non requise; ce runbook applique les obligations de recherche déjà publiées.

## Scénario BDD

- Given une question nécessite une recherche approfondie multi-sources.
- When l'utilisateur demande une synthèse traçable.
- Then la couverture, les contradictions, les dépendances de claims et les statuts publics sont visibles sans conclure par défaut.

## Procédure

- Précondition: la question possède un mandat explicite; une recherche approfondie ne complète pas silencieusement une conversation insuffisante.
- Commande vérifiée:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1
```

- Résultat attendu: plan de recherche, collecte multi-sources, couverture insuffisante, contradiction et synthèse traçable restent conformes.
- Erreur explicite: couverture insuffisante, contradiction non résolue ou source invalide produit un statut public non ambigu.
- Preuve à conserver: sortie du validateur, plan de recherche, sources retenues, claims résolus et statut public final.

## Statuts publics

| Statut public | Usage |
|---|---|
| `SUPPORTED` | Synthèse supportée par sources indépendantes. |
| `PARTIALLY_SUPPORTED` | Couverture partielle explicitement nommée. |
| `INSUFFICIENT_EVIDENCE` | Couverture insuffisante, pas de conclusion affirmative. |
| `CONFLICTING_EVIDENCE` | Contradictions visibles et qualifiées. |

## Garde-fous

- Obligations de recherche visibles avant synthèse.
- Aucun score de similarité traité comme preuve.
- Aucun fournisseur distant de secours.
- Fallback silencieux: interdit.
- Les écarts KA et RA différés restent visibles avant tout verdict V1.
