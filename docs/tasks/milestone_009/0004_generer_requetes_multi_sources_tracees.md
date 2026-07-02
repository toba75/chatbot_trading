# T-004 - Générer des requêtes multi-sources tracées

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, phase recherche approfondie et intégration KA.
- Objectif métier: transformer le plan de recherche en requêtes traçables couvrant plusieurs composants documentaires.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, consommant KA par le port publié.
- Objectif métier: rechercher des preuves par composant du plan sans dépendre de l'ordre non déterministe des résultats.
- Langage ubiquitaire: sous-requête, recherche multi-requêtes, `KnowledgeSearch`, trace de recherche, obligation couverte, projection versionnée.
- Invariants critiques: chaque sous-requête rattache son obligation de couverture; les versions de projection sont enregistrées; RA ne connaît aucun détail Qdrant.
- Garde-fous: aucun accès direct à Qdrant; aucune requête non liée au plan; aucune limite de résultat implicite; aucun ordre de callback utilisé comme décision métier.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-003 terminé.
- Présence des milestones amont dans master: M-005 et M-008 présents via `master`.
- Décisions manquantes: aucune si RA continue à consommer KA par port; ADR requise si un nouveau moteur de recherche externe durable est introduit.
- Risques: sur-représenter un seul composant; perdre la traçabilité projection; confondre requêtes FR/EN et traduction libre non vérifiable.

## Tâches
### T-004 - Générer des requêtes multi-sources tracées
- But métier: collecter des candidats pour toutes les obligations du plan sans masquer les composants non couverts.
- Portée DDD: `DeepEvidenceSearchRequest`, génération de sous-requêtes FR/EN, port `KnowledgeSearch`, association obligation -> trace KA, version de projection et limite explicite.
- Scénario BDD:
  - Given un plan approfondi contient trois obligations de couverture.
  - When RA génère les requêtes multi-sources.
  - Then chaque obligation produit au moins une requête tracée vers KA avec limite explicite et version de projection enregistrée.
- Tests d'acceptation à écrire: `tests/m009/validate_multi_query_search_acceptance.ps1`, qui échoue tant que chaque obligation n'est pas recherchée séparément et tracée.
- Tests unitaires à écrire: tests pour obligation sans requête, requête hors plan, limite absente, projection absente, résultat sans trace KA, ordre de résultats non déterministe et champ Qdrant exposé.
- Implémentation attendue: créer `app/research_answering/application/run_deep_research.py` ou un module dédié de requêtes, étendre le port KA consommé par RA, enregistrer les traces par obligation et refuser toute requête sans plan.
- Invariants et garde-fous: aucune requête hors mandat; aucune collection Qdrant dans RA; aucune limite par défaut; aucune synthèse possible si une obligation n'a pas été interrogée.
- Dépendances: T-003; `app/knowledge_access/application/search_knowledge.py`; `SearchTraceRecord`; `ResearchPlan`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_search_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_search_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir recherches multi requetes`
- Commit GREEN: `feat(m009): rechercher preuves multi sources tracees`

