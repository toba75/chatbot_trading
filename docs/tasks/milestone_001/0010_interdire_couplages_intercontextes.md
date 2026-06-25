# T-010 - Interdire les couplages intercontextes

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, tests et gates `détection automatisée des dépendances intercontextes interdites`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 13, 20 et 21.
- Objectif métier: empêcher l'érosion des frontières DDD une fois les modules et contrats publiés.

## Contexte DDD
- Domaine: architecture applicative orientée domaine.
- Bounded context: transverse, avec contrôle sur SP, KA, EG, RA, CV, SD, EX et `platform`.
- Objectif métier: garantir que les contextes communiquent par contrats publiés ou façades applicatives au lieu d'importer les modèles internes.
- Langage ubiquitaire: dépendance autorisée, import interdit, modèle interne, façade applicative, couche domaine, adaptateur, cycle de dépendance.
- Invariants critiques: `domain` ne dépend pas des frameworks ni adaptateurs; un contexte n'importe pas les agrégats internes d'un autre; les cycles intercontextes sont interdits; les modèles d'API ne sont pas des entités de domaine.
- Garde-fous: tests d'architecture exécutables; refus explicite des imports interdits; aucune liste blanche implicite pour contourner un échec.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN; T-003 matérialise les modules; T-004 à T-009 publient les contrats utilisés comme chemins autorisés.
- Présence des milestones amont dans master: M-000 est présent dans `master`.
- Décisions manquantes: aucune ADR nouvelle si la tâche applique DDD-ADR-001 et les règles d'architecture v4.1.
- Risques: laisser passer un couplage parce que le module est encore vide; confondre import de contrat publié et import d'agrégat interne; autoriser un cycle par commodité.

## Tâches
### T-010 - Interdire les couplages intercontextes
- But métier: rendre les frontières DDD vérifiables automatiquement avant les comportements métier aval.
- Portée DDD: tests d'architecture pour imports de couches, imports intercontextes, cycles, dépendances externes dans `domain` et séparation entre contrats publiés et modèles internes.
- Scénario BDD:
  - Given un contexte tente d'utiliser le modèle interne d'un autre contexte.
  - When les tests d'architecture sont exécutés.
  - Then l'import interdit est refusé et le contrat publié attendu est nommé.
- Tests d'acceptation à écrire: un test qui injecte un import intercontexte interdit dans un échantillon contrôlé et vérifie que la gate échoue avec le contexte producteur et consommateur.
- Tests unitaires à écrire: tests du graphe d'import, classification des packages `domain`, `application`, `adapters`, détection de cycle et distinction entre contrat publié autorisé et agrégat interne interdit.
- Implémentation attendue: créer un validateur d'architecture ou une suite de tests qui inspecte les imports Python et échoue sur les violations des règles M-001.
- Invariants et garde-fous: aucune liste blanche non documentée; aucun import adaptateur dans `domain`; aucun cycle masqué; aucun `try/catch` qui transforme une analyse incomplète en GREEN.
- Dépendances: T-003; T-004; T-005; T-006; T-007; T-008; T-009; DDD-ADR-001.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_architecture_boundaries_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_architecture_boundaries_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m001): couvrir les couplages intercontextes interdits`.
- Commit GREEN: `feat(m001): verrouiller les frontières d'import`.
