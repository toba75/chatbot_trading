# T-003 - Planifier une recherche avec obligations de couverture

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, spécification v4.1 section RA et phase de recherche approfondie.
- Objectif métier: décomposer une question en plan vérifiable avant toute collecte multi-sources.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: garantir qu'une analyse approfondie couvre explicitement les composants de la question, les arguments favorables, défavorables, limites et lacunes.
- Langage ubiquitaire: `ResearchPlan`, `SubQuestion`, `CoverageObligation`, `ResearchMode`, plan de recherche approfondie, mandat retenu.
- Invariants critiques: une recherche approfondie DOIT comporter un plan et des obligations de couverture; chaque obligation est nommée avant collecte; une obligation vide bloque la recherche.
- Garde-fous: aucune obligation par défaut; aucune sous-question implicite non tracée; aucun plan produit depuis un historique conversationnel brut.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-002 terminé.
- Présence des milestones amont dans master: M-008 présent, notamment question résolue autonome et mode `RECHERCHE_APPROFONDIE`.
- Décisions manquantes: aucune si le planificateur reste déterministe et local; ADR requise si un planificateur externe durable devient source de décision.
- Risques: créer des sous-questions trop techniques; ignorer une dimension du mandat; traiter la recherche approfondie comme simple variante de `DOCUMENTARY_SIMPLE`.

## Tâches
### T-003 - Planifier une recherche avec obligations de couverture
- But métier: rendre visible ce qui doit être couvert avant d'interroger KA et EG.
- Portée DDD: extension de `ResearchMode` pour le mode approfondi, `ResearchPlanningPolicy`, `ResearchPlan`, `SubQuestion`, `CoverageObligation` et événement `ResearchPlanCreated`.
- Scénario BDD:
  - Given une question autonome demande de comparer volatility targeting et Kelly avec conditions d'application.
  - When RA planifie la recherche approfondie.
  - Then le plan contient des sous-questions et obligations couvrant méthodes, conditions, preuves favorables, preuves défavorables, limites et lacunes attendues.
- Tests d'acceptation à écrire: `tests/m009/validate_deep_research_planning_acceptance.ps1`, qui échoue tant que RA ne produit pas de plan approfondi avec obligations nommées.
- Tests unitaires à écrire: tests pour mode approfondi absent, mandat incomplet, obligation vide, obligation dupliquée, sous-question sans obligation, historique brut fourni comme source, planification dupliquée et événement sans version de politique.
- Implémentation attendue: étendre `app/research_answering/domain/research_case.py`, créer ou étendre `app/research_answering/domain/research_planning.py`, ajouter les commandes applicatives de planification approfondie et persister le plan dans le ResearchCase.
- Invariants et garde-fous: aucun plan sans mandat explicite; aucune collecte avant plan; aucun mode implicite; aucune sous-question hors mandat; aucune règle financière inventée.
- Dépendances: T-002; M-008 `ConversationMode.RECHERCHE_APPROFONDIE`; `ResolvedQuestion`; `ResearchMandate`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_planning_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_planning_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir plan recherche approfondie`
- Commit GREEN: `feat(m009): planifier recherche approfondie`

