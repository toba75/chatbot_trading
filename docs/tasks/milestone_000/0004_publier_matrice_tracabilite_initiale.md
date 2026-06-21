# T-004 - Publier la matrice de traçabilité initiale

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrable `matrice initiale exigence -> test -> code -> ADR`, et spécification v4.1, section 21.
- Objectif métier: relier les exigences normatives aux preuves d'implémentation avant d'ajouter des comportements métier.

## Contexte DDD
- Domaine: traçabilité de gouvernance.
- Bounded context: transverse.
- Objectif métier: rendre visible la chaîne exigence, test, code et décision pour éviter les écarts silencieux entre spécification et implémentation.
- Langage ubiquitaire: exigence, preuve de test, artefact de code, ADR, statut de couverture, justification.
- Invariants critiques: une exigence suivie possède un identifiant stable; un lien manquant est explicite; une ADR mentionnée dans la matrice existe; une preuve de test pointe vers une commande ou un fichier vérifiable.
- Garde-fous: aucun statut implicite; aucune cellule vide; aucune exigence critique supprimée sans trace.

## Blocages Ou Préconditions
- État GREEN/RED connu: aucune matrice de traçabilité n'est visible dans le dépôt.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont.
- Décisions manquantes: aucune décision structurante nouvelle; la matrice référence les ADR existantes sans changer leur sens.
- Risques: déclarer une exigence couverte sans test automatisé ou sans commande de validation.

## Tâches
### T-004 - Publier la matrice de traçabilité initiale
- But métier: fournir le premier artefact qui relie les exigences M-000 aux tests, scripts, documents et ADR.
- Portée DDD: gouvernance transverse; traçabilité minimale avant les contextes métier.
- Scénario BDD:
  - Given une exigence normative issue de la spécification v4.1 ou du plan de milestones.
  - When la matrice de traçabilité est contrôlée.
  - Then l'exigence possède un statut, une preuve de test, un artefact cible et une référence ADR explicite ou une justification d'absence d'ADR.
- Tests d'acceptation à écrire: un test qui échoue si une ligne de matrice contient une cellule vide, référence une ADR inexistante, référence un test absent ou déclare `Couvert` sans commande de validation.
- Tests unitaires à écrire: tests du parseur de matrice, du contrôle de statut autorisé, du contrôle des chemins de fichiers et du contrôle des références ADR.
- Implémentation attendue: créer `docs/traceability/matrix.md` ou un emplacement équivalent documenté; y inscrire les exigences initiales de M-000; créer un validateur strict de la matrice.
- Invariants et garde-fous: aucune couverture implicite; les statuts autorisés doivent être définis; une absence de code métier doit être déclarée comme hors portée de M-000, pas comme réussite silencieuse.
- Dépendances: T-001; T-002; plan de milestones; critères d'acceptation DDD de la section 21.
- Commandes de validation: future commande `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`; puis `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1` après T-006.
- Commit RED: `test(m000): couvrir la matrice de traçabilité initiale`.
- Commit GREEN: `feat(m000): publier la traçabilité initiale`.
