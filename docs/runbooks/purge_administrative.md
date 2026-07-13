# Runbook purge administrative M-013

## Statut

- Identifiant: `M013-Runbook-AdministrativePurge-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Preuve source: `docs/governance/m013_retention_policy.md`
- ADR applicables: DDD-ADR-010, DDD-ADR-012, DDD-ADR-004, ADR-010.
- ADR: non requise; ce runbook applique DDD-ADR-012 sans changer la politique de rétention.

## Scénario BDD

- Given une demande de purge administrative cible des conversations ou une projection régénérable.
- When l'opérateur contrôle justification, audit, cible et compatibilité de lecture.
- Then la purge administrative refuse toute suppression ordinaire, conserve les résultats négatifs et ne cascade pas vers KA, EG, RA, SD ou EX.

## Purge administrative

- Précondition: la demande porte une justification administrative, un audit event id et des identifiants stables non dupliqués.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: la politique `M013-RetentionPolicy-1.0` accepte uniquement `LOGICAL_ARCHIVE`, `PURGE_CONVERSATION_CONTENT` ou `PURGE_REGENERABLE_PROJECTION`.
- Erreur explicite: suppression ordinaire interdite, cascade conversationnelle interdite, cible de projection sous source SP interdite ou résultat négatif non conservé.
- Preuve à conserver: sortie du validateur, `docs/governance/m013_retention_policy.md` et l'audit event id.

## Reconstruction projection KA

- Précondition: les originaux SP et versions canoniques existent sous la racine d'autorité.
- Commande vérifiée:

```console
uv run --locked gate
```

- Résultat attendu: `projection_manifest.json` est produit dans la cible KA hors racine SP.
- Erreur explicite: source SP manquante, marqueurs d'autorité absents ou cible KA non vide.
- Preuve à conserver: manifeste de projection, sortie du script et identifiants stables reconstruits.

## Garde-fous

- Aucune purge ordinaire.
- Aucun résultat négatif ou supersédé supprimé silencieusement.
- Aucune cascade depuis CV vers connaissances, réponses, stratégies ou expériences publiées.
