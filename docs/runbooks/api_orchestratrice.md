# Runbook déprécié : API orchestratrice isolée

## Statut

Cette procédure de déploiement isolé est dépréciée depuis ADR-046. L'API
orchestratrice reste réelle et publique derrière Caddy, mais elle est désormais
un service interne de la pile choisie. Ce document ne constitue plus un chemin
de démarrage.

Le runbook actif est
`docs/runbooks/environnements_explicites.md`. L'opérateur utilise exclusivement
l'une des commandes suivantes :

```console
uv run development
uv run test
uv run production
```

| Profil | Autorité HTTPS locale | Configuration complète |
|---|---|---|
| `development` | `https://localhost:18443` | `config/environments/development.yaml` |
| `test` | `https://localhost:19443` | `config/environments/test.yaml` |
| `production` | `https://localhost:20443` | `config/environments/production.yaml` |

Seul Caddy publie un port hôte. L'API, PostgreSQL, Qdrant, le gateway LLM et les
quatre instances workers restent internes au projet Compose du profil. Les
opérations d'administration reçoivent explicitement le même profil et refusent
toute identité de stockage divergente avant effet.

## Contrôles actifs

- readiness publique via l'autorité HTTPS du profil ;
- validation de la CA Caddy exportée, sans désactivation TLS ;
- progression publique persistée des actions réellement câblées ;
- deux workers documentaires et deux workers de projection identifiés ;
- quatorze conteneurs attendus au total ;
- aucune suppression automatique des volumes development ou production.

```console
uv run --locked gate --scope m013_environments --offline
uv run --locked gate --scope m013_environments --live
```

Une erreur de certificat, d'identité, de cardinalité ou de révision rend la
preuve live terminalement RED. Aucun runtime alternatif n'est démarré.
