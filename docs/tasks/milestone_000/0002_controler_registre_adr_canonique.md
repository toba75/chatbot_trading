# T-002 - Contrôler le registre ADR canonique

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-000 - Gouvernance exécutable`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3.
- Objectif métier: garantir que les décisions structurantes sont visibles, indexées et vérifiables avant l'implémentation.

## Contexte DDD
- Domaine: gouvernance des décisions d'architecture.
- Bounded context: transverse.
- Objectif métier: empêcher qu'une décision structurante change ou apparaisse sans trace ADR contrôlée.
- Langage ubiquitaire: ADR, statut, remplacement, décision structurante, index ADR, impact d'implémentation, liens de traçabilité.
- Invariants critiques: toute ADR doit être indexée; tout statut doit appartenir à la liste autorisée; une ADR acceptée ne change pas de sens silencieusement; le registre ne peut pas être considéré valide si une ADR référencée par la spécification manque.
- Garde-fous: validation automatisée du format, de l'index et des champs obligatoires; absence de tolérance silencieuse sur les noms ou statuts.

## Blocages Ou Préconditions
- État GREEN/RED connu: le script `scripts/validate_adr_system.ps1` existe et passe sur 19 ADR contrôlées.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont.
- Décisions manquantes: aucune ADR M-000 nouvelle n'est identifiée; la tâche consolide le contrôle du registre existant.
- Risques: laisser le script valider la forme sans contrôler l'alignement minimal avec les décisions listées dans la spécification v4.1.

## Tâches
### T-002 - Contrôler le registre ADR canonique
- But métier: rendre le registre ADR vérifiable comme artefact canonique de décision.
- Portée DDD: gouvernance transverse des décisions; aucun changement de sens des ADR acceptées.
- Scénario BDD:
  - Given la spécification v4.1 liste les décisions techniques et DDD structurantes.
  - When la validation du registre ADR est exécutée.
  - Then chaque ADR versionnée respecte le format attendu, apparaît dans l'index et correspond à une décision référencée ou explicitement ajoutée.
- Tests d'acceptation à écrire: un test qui échoue si une ADR est absente de `docs/adr/index.md`, si un statut n'est pas autorisé ou si une décision structurante de la section 3 n'est pas matérialisée dans `docs/adr/`.
- Tests unitaires à écrire: tests du contrôle de nommage `ADR-###-*` et `DDD-ADR-###-*`, du contrôle de statut, du contrôle des sections obligatoires et du contrôle des liens depuis l'index.
- Implémentation attendue: compléter ou conserver `scripts/validate_adr_system.ps1` en validateur strict du registre ADR; documenter la commande dans la future gate M-000; ne pas modifier le sens des ADR existantes.
- Invariants et garde-fous: aucune ADR non indexée; aucun statut implicite; aucune correction automatique de nom ou de statut; aucun remplacement d'ADR sans nouvelle ADR et mise à jour de l'index.
- Dépendances: T-001; `docs/adr/README.md`; `docs/adr/TEMPLATE.md`; `docs/adr/index.md`; section 3 de la spécification.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1`.
- Commit RED: `test(m000): couvrir le contrôle canonique du registre ADR`.
- Commit GREEN: `feat(m000): renforcer la validation du registre ADR`.
