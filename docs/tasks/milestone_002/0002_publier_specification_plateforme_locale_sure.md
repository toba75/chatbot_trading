# T-002 - Publier la spécification de plateforme locale sûre

## Milestone
- Nom: M-002 - Plateforme locale sûre.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables M-002, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 13, 15, 16, 18, 19, 20 et 21.
- Objectif métier: transformer les règles de plateforme v4.1 en spécification M-002 exécutable avant l'implémentation technique.

## Contexte DDD
- Domaine: exécution locale sûre et auditable.
- Bounded context: `platform`, sans devenir un bounded context métier.
- Objectif métier: définir comment les contextes métier obtiennent jobs, livraison d'événements et inférence LLM sans exposer les données ni masquer les pannes.
- Langage ubiquitaire: hôte Docker local, Spark d'inférence, gateway LLM, outbox transactionnelle, job priorisé, appel d'inférence, panne explicite, observabilité technique.
- Invariants critiques: le Spark calcule des inférences seulement; `docker-local` possède le domaine et les données; le gateway ne prend aucune décision métier; les jobs ne sont pas des événements de domaine.
- Garde-fous: ne pas créer de microservice métier; ne pas introduire un fournisseur distant de secours; ne pas coder en dur un endpoint Spark dans le domaine.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit être GREEN.
- Présence des milestones amont dans master: M-000 et M-001 sont présents dans `master`.
- Décisions manquantes: aucune si la spécification applique ADR-007, ADR-008, ADR-009, DDD-ADR-006 et DDD-ADR-008 sans changer leur sens; une ADR est requise si mTLS devient obligatoire ou si un service est déplacé hors `docker-local`.
- Risques: mélanger règles de domaine et règles de transport; planifier le Compose avant les invariants; dupliquer les contrats M-001.

## Tâches
### T-002 - Publier la spécification de plateforme locale sûre
- But métier: rendre le périmètre M-002 vérifiable par des scénarios et des critères d'acceptation avant toute configuration ou code.
- Portée DDD: document `docs/specs/m002_plateforme_locale_sure.md`, langage de plateforme, responsabilités `platform`, relations avec les contrats M-001 et ADR applicables.
- Scénario BDD:
  - Given la spécification v4.1 impose deux plans physiques et une cohérence éventuelle par outbox.
  - When la spécification M-002 est publiée.
  - Then chaque règle de plateforme nomme le comportement attendu, les invariants, les tests et les ADR qui la gouvernent.
- Tests d'acceptation à écrire: un test qui valide la présence des sections M-002, des scénarios Given-When-Then, des règles `docker-local`/`spark-inference`, du gateway unique, de l'outbox et des commandes de validation.
- Tests unitaires à écrire: tests du validateur de spécification pour section manquante, ADR absente, règle de placement incohérente, fallback silencieux ou endpoint Spark codé en dur.
- Implémentation attendue: créer `docs/specs/m002_plateforme_locale_sure.md` et un validateur PowerShell dédié, sans implémenter encore la plateforme.
- Invariants et garde-fous: aucune règle implicite; aucune valeur par défaut non documentée; aucun comportement alternatif silencieux; aucune modification de sens d'une ADR acceptée.
- Dépendances: T-001; ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-008; `docs/specs/m001_frontieres_ddd_contrats_publies.md`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m002_specification.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m002): couvrir la spécification de plateforme locale`.
- Commit GREEN: `docs(m002): publier la spécification de plateforme locale`.
