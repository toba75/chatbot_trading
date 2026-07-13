# Runbook lecture du rapport d'acceptation V1 M-013

## Statut

- Identifiant: `M013-Runbook-V1AcceptanceReport-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Preuve source: `docs/governance/m013_v1_acceptance_report.md`
- ADR applicables: ADR-010, DDD-ADR-010, DDD-ADR-011.
- ADR: non requise; ce runbook explique la lecture du verdict final sans modifier les critères V1.

## Scénario BDD

- Given le rapport d'acceptation V1 agrège les décisions d'écarts et les gates finales.
- When l'utilisateur lit le verdict, les critères et les sorties capturées.
- Then les écarts différés ou bloquants interdisent l'acceptation V1 tant qu'ils ne sont pas acceptés ou corrigés explicitement.

## Lecture du verdict

- Précondition: le rapport `M013-V1AcceptanceReport-1.0` et la matrice de traçabilité sont présents.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: le verdict final reste `non acceptée` si SP, KA, RA, SD ou LLM restent non acceptés.
- Erreur explicite: critère V1 absent, preuve de sortie absente, commande finale absente ou verdict final incohérent.
- Preuve à conserver: sortie du validateur et `docs/governance/m013_v1_acceptance_report.md`.

## Traçabilité du rapport

- Précondition: chaque exigence `REQ-M013-001` à `REQ-M013-012` est reliée à un test, une commande, un code ou document et une ADR ou justification.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: la traçabilité confirme le lien entre T-012, les gates finales, les écarts V1 et la définition de terminé.
- Erreur explicite: exigence M-013 absente, commande manquante, source documentaire absente ou justification ADR insuffisante.
- Preuve à conserver: sortie du validateur de traçabilité et ligne `REQ-M013-012`.

## Garde-fous

- Aucune acceptation implicite d'un écart différé.
- Aucune correction silencieuse d'un écart bloquant.
- Aucune promesse financière dérivée du verdict V1.
