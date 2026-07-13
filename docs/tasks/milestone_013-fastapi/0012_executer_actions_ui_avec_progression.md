# T-012 - Exécuter les actions UI avec progression publique

## Milestone

- Nom : M13-FastAPI - API orchestratrice ASGI raccordée.
- Source : ADR-031 proposée, UI-019 et constat du diagnostic local bloqué.
- Objectif métier : toute action exposée par l’UI est réellement exécutable et
  son avancement public reste cohérent jusqu’à son issue.

## Contexte DDD

- Domaine : exécution asynchrone observable d’une action utilisateur.
- Bounded contexts propriétaires : SP possède le diagnostic et son état ;
  platform supervise le runtime local ; UI consomme exclusivement le contrat
  public.
- Langage ubiquitaire : action, file, exécution, progression, issue terminale.
- Invariant critique : l’UI ne rend jamais disponible une action dont la chaîne
  `API -> outbox -> relais -> worker -> état public` manque.

## Scénario BDD

- Given `uv run ui` prépare une action documentaire asynchrone et tous ses
  participants réels.
- When l’utilisateur demande un diagnostic puis consulte le corpus pendant son
  exécution.
- Then le worker réel consomme l’outbox, l’UI affiche une progression publique
  `QUEUED` ou `RUNNING` avec les comptes persistés, se rafraîchit jusqu’à
  l’issue `SUCCEEDED` ou `FAILED` et n’invente aucun état de remplacement.

## Tests et implémentation attendus

- Test d’acceptation : le parcours navigateur réel constate une phase non
  terminale, puis le diagnostic réel terminé via le worker supervisé.
- Tests unitaires : transitions `MANIFEST_CREATED -> DIAGNOSING -> DIAGNOSED`,
  mapping de progression, rendu générique et ordre de supervision.
- Implémentation : démarrer le worker documentaire réel dans la stack locale,
  publier le contrat générique de progression et l’afficher avec
  rafraîchissement borné tant qu’il est non terminal.
- Garde-fous : aucun accès UI aux tables, à l’outbox, au worker ou aux logs ;
  aucun compteur synthétique ; arrêt inverse des processus supervisés.

## Dépendances et preuves

- Dépendances : T-006, T-007, T-010, T-011 ; ADR-018, ADR-024, ADR-025,
  ADR-030 et ADR-031.
- Commande de validation finale : `uv run --locked gate`.
- Commit RED : `b40f92b6f`, `test(ui): couvrir action réelle et progression ADR-031`.
- Commit GREEN : `245410d75`, `feat(ui): exécuter diagnostics et afficher progression ADR-031`.
