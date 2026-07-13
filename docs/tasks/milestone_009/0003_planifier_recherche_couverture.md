# T-003 - Planifier la recherche approfondie par obligations de couverture

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: spécification v4.1 sections 8 et 12, plan M-009, et spécification M-009 publiée par T-002.
- Objectif métier: transformer une question résolue et un mandat en plan approfondi explicite avant toute collecte de preuves.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: empêcher qu'une synthèse globale soit produite depuis une recherche implicite ou mono-requête.
- Langage ubiquitaire: `ResearchCase`, `ResearchMode.DEEP_RESEARCH`, `DeepResearchPlan`, sous-question, obligation de couverture, mandat, méthode, preuve favorable, preuve défavorable, limite, lacune, politique de planification.
- Invariants critiques: le mode approfondi est demandé explicitement; chaque sous-question appartient au mandat; les obligations de couverture sont nommées avant la collecte; un plan vide ou non déterministe est refusé.
- Garde-fous: aucun mode par défaut; aucune extension du mandat utilisateur; aucune sous-question hors univers ou horizon autorisé; aucun plan fondé uniquement sur mots-clés non audités.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 terminés.
- Présence des milestones amont dans master: M-008 présent.
- Décisions manquantes: aucune si la planification reste dans RA; ADR requise si un planificateur externe durable devient source de décision métier.
- Risques: surcharger le planificateur M-007 documentaire simple; mélanger plan de recherche RA et stratégie SD; oublier les obligations de preuves défavorables ou de limites.

## Tâches
### T-003 - Planifier la recherche approfondie par obligations de couverture
- But métier: ouvrir un cas de recherche approfondie avec un plan vérifiable et complet.
- Portée DDD: extension contrôlée de `ResearchMode`, politique `DeepResearchPlanningPolicy`, `SubQuestion`, `CoverageObligation`, événements `ResearchPlanCreated`, validation du mandat et refus des plans incomplets.
- Scénario BDD:
  - Given une question autonome demande une synthèse multi-sources sur Kelly et volatility targeting avec un mandat explicite.
  - When RA planifie la recherche approfondie.
  - Then le `ResearchCase` passe à `PLANNED` avec des sous-questions et des obligations couvrant méthodes, preuves favorables, preuves défavorables, dépendances, limites et zones non documentées.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que RA ne sait pas créer un plan approfondi depuis un mandat explicite.
- Tests unitaires à écrire: tests de `ResearchMode` pour `DEEP_RESEARCH`, de `DeepResearchPlanningPolicy` pour sous-questions vides, obligation dupliquée, obligation hors mandat, absence de preuve défavorable, absence de limite, mode documentaire simple refusé et plan non déterministe.
- Implémentation attendue: étendre `app/research_answering/domain/research_case.py`, `app/research_answering/domain/research_planning.py` et `app/research_answering/application/open_research_case.py` sans casser M-007; créer les objets-valeur nécessaires au plan approfondi; conserver une politique M-007 séparée si elle reste documentaire simple.
- Invariants et garde-fous: plan obligatoire avant collecte; mode approfondi explicite; pas de sous-question hors mandat; pas de fallback vers `DOCUMENTARY_SIMPLE`.
- Dépendances: T-002; `app/research_answering/domain/research_case.py`; `app/research_answering/domain/research_planning.py`; `uv run --locked gate`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m009): couvrir planification recherche approfondie`
- Commit GREEN: `feat(m009): planifier recherche approfondie`
