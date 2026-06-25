# T-006 - Assembler les commandes de validation initiales

## Milestone
- Nom: M-000 - Gouvernance exécutable.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `commandes de validation initiales` et sortie attendue `le projet sait dire GREEN ou RED sans ambiguïté`.
- Objectif métier: fournir les commandes standard qui pilotent l'état de gouvernance du projet.

## Contexte DDD
- Domaine: gouvernance exécutable.
- Bounded context: transverse.
- Objectif métier: permettre à l'équipe et aux agents d'exécuter une gate unique de test et une gate unique de lint avant chaque implémentation.
- Langage ubiquitaire: commande de validation, test, lint, gate, GREEN, RED, script requis, erreur explicite.
- Invariants critiques: `scripts/test.ps1` et `scripts/lint.ps1` existent; une commande échoue si un validateur requis manque; une commande ne masque pas un RED; la sortie nomme le validateur en échec.
- Garde-fous: agrégation stricte des validations M-000; pas de passage silencieux quand aucune suite n'est exécutée; pas de comportement alternatif implicite si un outil est absent.

## Blocages Ou Préconditions
- État GREEN/RED connu: au début de M-000, les commandes `scripts/test.ps1` et `scripts/lint.ps1` sont absentes; `scripts/validate_adr_system.ps1` est la seule validation existante.
- Présence des milestones amont dans master: M-000 n'a aucune dépendance amont.
- Décisions manquantes: ADR-010 documente la décision durable de gates PowerShell; aucune autre décision structurante n'est manquante.
- Risques: faire réussir une commande parce que le dépôt n'a pas encore de code applicatif; oublier d'ajouter les validations ADR, tâches, traçabilité et définition de terminé.

## Tâches
### T-006 - Assembler les commandes de validation initiales
- But métier: livrer les commandes minimales qui rendent M-000 mesurable et réutilisable par les milestones suivants.
- Portée DDD: gouvernance transverse; orchestration de validateurs documentaires et de scripts, sans implémentation métier applicative.
- Scénario BDD:
  - Given les artefacts de gouvernance M-000 sont présents.
  - When `.\scripts\test.ps1` et `.\scripts\lint.ps1` sont exécutés.
  - Then les validations ADR, tâches, traçabilité et définition d'achèvement sont exécutées, et la commande retourne GREEN ou RED avec une cause explicite.
- Tests d'acceptation à écrire: un test qui exécute `scripts/test.ps1` et `scripts/lint.ps1` en succès sur le dépôt valide, puis vérifie qu'une validation manquante ou échouée provoque un code de sortie non nul et un message ciblé.
- Tests unitaires à écrire: tests de l'agrégateur de commandes, du contrôle d'existence des scripts requis, du code de sortie et du format des messages d'erreur.
- Implémentation attendue: créer `scripts/test.ps1` et `scripts/lint.ps1`; brancher les validateurs produits par T-002 à T-005; documenter le périmètre exact des commandes M-000.
- Invariants et garde-fous: aucune validation requise ne peut être ignorée; aucune réussite n'est produite si un script requis manque; l'absence de suite applicative est mentionnée comme hors portée de M-000 uniquement si elle est documentée dans la matrice de traçabilité.
- Dépendances: T-002; T-003; T-004; T-005.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_adr_system.ps1`.
- Commit RED: `test(m000): couvrir les commandes de validation initiales`.
- Commit GREEN: `feat(m000): assembler les gates test et lint`.
