# T-003 - Déclarer les contextes et propriétaires de données

## Milestone
- Nom: M-001 - Frontières DDD et contrats publiés.
- Source: `docs/specs/plan_implementation_milestones_workstreams.md`, livrables `modules de contexte avec couches domain, application, adapters`, et `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 4, 13, 14 et 21.
- Objectif métier: rendre les sept contextes identifiables dans le code et dans la documentation avant toute logique métier avancée.

## Contexte DDD
- Domaine: structuration du monolithe modulaire et propriété logique des données.
- Bounded context: SP, KA, EG, RA, CV, SD et EX.
- Objectif métier: permettre à chaque comportement futur de trouver son contexte propriétaire sans accès croisé aux modèles internes.
- Langage ubiquitaire: contexte propriétaire, responsabilité exclusive, couche `domain`, couche `application`, couche `adapters`, stockage possédé, artefact possédé.
- Invariants critiques: chaque contexte a un module distinct; chaque module a ses couches prévues; chaque stockage indicatif a un propriétaire unique; `platform` reste un support technique, pas un contexte métier.
- Garde-fous: créer des modules vides ou minimaux sans logique défensive; ne pas implémenter les agrégats métier avant les scénarios dédiés des milestones aval.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 doit avoir restauré les gates M-000 avant création des modules.
- Présence des milestones amont dans master: M-000 est présent dans `master`; M-001 dépend uniquement de M-000.
- Décisions manquantes: aucune ADR nouvelle si la structure applique DDD-ADR-001 et les règles de dépendance existantes.
- Risques: créer une arborescence décorative non testée; confondre `platform` avec un bounded context métier; introduire des dépendances externes dans `domain`.

## Tâches
### T-003 - Déclarer les contextes et propriétaires de données
- But métier: matérialiser le monolithe modulaire pour que les frontières soient visibles et contrôlables.
- Portée DDD: création des modules `app/source_processing`, `app/knowledge_access`, `app/evidence_governance`, `app/research_answering`, `app/conversation`, `app/strategy_design`, `app/experimentation` et `app/platform` avec couches cibles.
- Scénario BDD:
  - Given les sept bounded contexts ont une responsabilité exclusive.
  - When l'arborescence applicative est contrôlée.
  - Then chaque contexte possède ses couches canoniques et aucun stockage n'a plusieurs propriétaires.
- Tests d'acceptation à écrire: un test d'architecture qui échoue tant que les sept modules et leurs couches `domain`, `application` et `adapters` ne sont pas présents et déclarés dans un registre de contextes.
- Tests unitaires à écrire: tests du registre de contextes refusant un code de contexte inconnu, un propriétaire de stockage dupliqué ou une couche absente.
- Implémentation attendue: créer les modules de contexte, un registre explicite des propriétaires de données et une documentation courte liant chaque module à sa responsabilité v4.1.
- Invariants et garde-fous: pas d'import de framework dans `domain`; pas de modèle métier dans `platform`; pas de propriétaire implicite; pas de valeur par défaut pour un contexte inconnu.
- Dépendances: T-001; T-002; DDD-ADR-001; section 14 de la spécification v4.1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_context_modules_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m001\validate_context_registry_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m001): couvrir les modules et propriétaires de contexte`.
- Commit GREEN: `feat(m001): déclarer les contextes propriétaires`.
