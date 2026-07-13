# T-004 - Préserver les contrats publics existants

## Milestone

- Nom: M13-FastAPI - API orchestratrice ASGI raccordée.
- Source: runtime `orchestrator-api` existant, spécifications M-005, M-008 et M-013.
- Objectif métier: changer le transport sans changer silencieusement les réponses déjà publiées.

## Contexte DDD

- Domaine: conversation produit, évaluation et accès aux connaissances via la frontière publique.
- Bounded contexts: CV, RA, KA et évaluation; `platform` ne fait que déléguer.
- Objectif métier: conserver les statuts, corps et erreurs des clients existants pendant la migration.
- Langage ubiquitaire: parité contractuelle, erreur publique, endpoint non configuré, réponse conversationnelle.
- Invariants critiques: même requête et même dépendances produisent le même contrat public avant et après migration.
- Garde-fous: une route encore non configurée reste explicitement non configurée; aucun succès synthétique.

## Blocages Ou Préconditions

- T-003 GREEN.
- Inventaire exact des routes `local_runtime.py` requis avant RED.
- Risque: corriger opportunément un ancien comportement pendant une migration de transport.

## Tâches

### T-004 - Préserver les contrats publics existants

- But métier: migrer santé, conversation, benchmark LLM, recherche et indexation vers des routeurs ASGI sans régression observable.
- Portée DDD: adaptateurs HTTP et délégation vers les handlers existants; aucune modification des règles CV, RA ou KA.
- Scénario BDD:
  - Given un corpus de requêtes publiques capturant succès, refus et indisponibilités existants
  - When ces requêtes sont rejouées contre l'application ASGI
  - Then les statuts HTTP, codes d'erreur et champs publics restent identiques hors changement explicitement spécifié
- Tests d'acceptation à écrire: `uv run --locked gate`, comparant l'ancien adaptateur borné et le nouveau routeur.
- Tests unitaires à écrire: `uv run --locked gate`, couvrant validation des entrées et mapping des erreurs par route.
- Implémentation attendue: créer des `APIRouter` séparés par surface, déléguer aux fonctions/cas d'usage existants, puis retirer de `_local_post_response` uniquement les branches migrées.
- Invariants et garde-fous: pas de logique métier dans les fonctions de route; pas de `except Exception`; pas de modification de contrat non documentée.
- Dépendances: T-003; contrats M-005, M-008, M-013.
- Commandes de validation:
  - `uv run --locked gate`
  - `uv run --locked gate`
  - `uv run --locked gate`
- Commit RED: `test(api): couvrir parite contrats orchestrateur`.
- Commit GREEN: `refactor(api): migrer contrats existants vers asgi`.
