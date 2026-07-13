# T-003 - Ouvrir un cas de recherche avec mandat explicite

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA `ResearchCase`, `ResearchMandate`, politiques de planification et commandes RA.
- Objectif métier: créer une unité de recherche RA vérifiable avant toute collecte de preuves ou génération de réponse.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: figer une question autonome, un mandat et un plan local simple qui bornent la réponse attendue.
- Langage ubiquitaire: `ResearchCase`, `ResolvedQuestion`, `ResearchMandate`, `ResearchMode`, `ResearchPlan`, `CoverageObligation`, `OpenResearchCase`, `PlanResearch`.
- Invariants critiques: un `ResearchCase` possède une question autonome non vide et un mandat explicite; une recherche ne démarre pas sans obligations de couverture adaptées au mode.
- Garde-fous: aucune question implicite déduite de l'historique conversationnel; aucun mode par défaut; aucun accès CV ou KA direct depuis le domaine RA.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 terminés.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune si le plan local simple reste interne à RA; ADR requise si un planificateur externe durable ou une nouvelle politique de mode produit est introduit.
- Risques: confondre M-007 avec la conversation M-008; traiter l'historique comme preuve; générer des sous-questions non traçables.

## Tâches
### T-003 - Ouvrir un cas de recherche avec mandat explicite
- But métier: créer le point d'entrée RA qui transforme une question autonome et un mandat en cas de recherche planifié.
- Portée DDD: agrégat `ResearchCase`, objets-valeur `ResolvedQuestion`, `ResearchMandate`, `ResearchMode`, `ResearchPlan`, `CoverageObligation`, politique `ResearchPlanningPolicy`, commande `OpenResearchCase` et événement `ResearchCaseOpened`.
- Scénario BDD:
  - Given une question autonome et un mandat documentaire explicite.
  - When RA ouvre puis planifie le cas de recherche.
  - Then le cas passe à `PLANNED` avec des obligations de couverture nommées et sans utiliser l'historique conversationnel comme preuve.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant que RA ne crée pas un cas planifié à partir d'une question et d'un mandat explicites.
- Tests unitaires à écrire: tests pour question absente, mandat absent, mode inconnu, obligation de couverture vide, transition invalide, planification dupliquée, mutation du plan publié et tentative d'injecter un historique de conversation comme preuve.
- Implémentation attendue: ajouter les modèles de domaine RA nécessaires, le handler `OpenResearchCaseHandler`, le repository mémoire strict et un planificateur local déterministe pour M-007.
- Invariants et garde-fous: aucun mode implicite; aucune obligation de couverture par défaut; aucun accès aux preuves avant planification; aucun contenu conversationnel brut dans le cas de recherche.
- Dépendances: T-002; contrat `VerifiedResearchOutcome` M-001; context registry RA.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m007): couvrir cas recherche mandat explicite`
- Commit GREEN: `feat(m007): ouvrir cas recherche mandat explicite`
