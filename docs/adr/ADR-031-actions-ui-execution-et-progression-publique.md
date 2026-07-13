# ADR-031 - Actions UI exécutables et progression publique

**Statut :** Acceptée
**Date :** 2026-07-13
**Décideurs :** Équipe OSTrading
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** UI-019, incident de diagnostic local M13-FastAPI

## Contexte

L’UI locale pouvait accepter une action de diagnostic, persister son outbox et
masquer son bouton, sans démarrer le relais et le worker qui réalisent le
traitement. Le statut métier `MANIFEST_CREATED` était ainsi utilisé comme un
état d’affichage alors qu’il ne rendait ni l’attente, ni l’exécution, ni la
progression publique observables.

ADR-018 impose la frontière API orchestratrice et ADR-030 démarre l’API, la
base et le gateway nécessaires à l’UI. Aucune de ces décisions ne définissait
explicitement l’ensemble asynchrone requis par une action UI, ni le contrat
public de progression qui doit rester cohérent pendant son exécution.

## Décision

- Une action UI disponible **DOIT** disposer, avant son exposition, de toute sa
  chaîne d’exécution réelle : contrat public, écriture transactionnelle,
  outbox, relais, worker, persistance de l’issue et lecture publique.
- `uv run ui` **DOIT** superviser les participants réels requis par les actions
  qu’il rend disponibles. L’absence, l’arrêt ou l’échec de démarrage d’un
  participant **DOIT** bloquer le démarrage ; aucun worker synthétique, mock,
  stub ou fallback ne le remplace.
- Toute action asynchrone exposée publiquement **DOIT** publier un contrat de
  progression générique avec une phase (`NOT_REQUESTED`, `QUEUED`, `RUNNING`,
  `SUCCEEDED` ou `FAILED`), les unités réalisées, le total connu et l’erreur
  publique terminale éventuelle.
- Le statut métier de la ressource et la phase d’exécution sont distincts. Une
  transition d’exécution **DOIT** être persistée avant le travail réel ; les
  compteurs affichés ne **DOIVENT PAS** simuler une progression non persistée.
- L’UI **DOIT** rendre ce contrat par un composant générique et se rafraîchir
  tant que la phase est `QUEUED` ou `RUNNING`. Une action déjà demandée reste
  inspectable ; elle ne réapparaît pas comme disponible.
- La preuve d’acceptation **DOIT** exercer le parcours réel
  `UI -> API -> outbox -> relais -> worker -> état public`, constater une
  phase en cours, puis l’issue terminale sans manipuler les tables internes.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Démarrer et superviser le worker réel, avec contrat public de progression | Retenue | Rend l’action utilisable et observable de bout en bout. |
| Masquer le bouton après l’acceptation API | Rejetée | Produit un état bloqué indiscernable et viole « pas câblé, pas disponible ». |
| Déduire la progression depuis l’UI ou les logs | Rejetée | Introduit un état synthétique hors contrat public. |
| Remplacer le worker absent par une sortie simulée | Rejetée | Constitue un fallback interdit. |

## Conséquences

### Positives

- L’utilisateur voit une action en file, en cours, terminée ou échouée.
- Le bootstrap local est cohérent avec les actions qu’il rend disponibles.
- Le contrat générique peut être réutilisé par les prochaines actions longues.

### Négatives ou coûts

- Une dépendance de processus supplémentaire est supervisée localement.
- Les contrats publics, l’état SP et les preuves live évoluent ensemble.

### Risques et contrôles

- Un worker arrêté est détecté au démarrage et interdit la disponibilité UI.
- Les compteurs restent ceux des décisions réellement persistées.
- Les tests contrôlent l’ordre de démarrage, l’arrêt inverse, les transitions
  persistées et le parcours réel complet.

## Impact d'implémentation

- Modules concernés : `app/platform/ui_local_stack.py`, worker SP, contrats et
  read-models publics, client et rendu UI.
- Configuration concernée : runtime temporaire de `uv run ui` uniquement.
- Tests attendus : gouvernance, unité des transitions/progression, contrat API,
  orchestration locale et parcours UI réel.
- Milestones concernées : M13-FastAPI.

## Liens de traçabilité

- Spécification : `docs/specs/ui.md` UI-019.
- Plan d'implémentation : `docs/tasks/milestone_013-fastapi/0012_executer_actions_ui_avec_progression.md`.
- Tests d'acceptation : `gate_tests/ported/tests/m013_fastapi/validate_ui_action_execution_progress_acceptance.py`,
  complété par la preuve locale réelle `uv run ui` sur un PDF du corpus.
- Commits : RED `b40f92b6f`; GREEN à compléter dans le journal de tâche.

## Notes

Cette décision complète ADR-018 et ADR-030 sans modifier leur sens. Elle est
acceptée après la preuve GREEN du parcours local réel et de la gate canonique.
