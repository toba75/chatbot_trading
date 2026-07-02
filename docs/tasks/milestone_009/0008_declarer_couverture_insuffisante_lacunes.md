# T-008 - Déclarer couverture insuffisante et lacunes

## Milestone
- Nom: M-009 - Recherche approfondie multi-sources.
- Source: plan M-009, spécification v4.1 sections couverture, abstention et lacunes documentaires.
- Objectif métier: produire un statut explicite quand la recherche approfondie ne couvre pas le mandat.

## Contexte DDD
- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA.
- Objectif métier: empêcher une synthèse approfondie de paraître complète quand des obligations de couverture ne sont pas satisfaites.
- Langage ubiquitaire: `KnowledgeGap`, obligation manquante, `INSUFFICIENT_EVIDENCE`, couverture documentaire, abstention fonctionnelle, raison publique.
- Invariants critiques: une lacune critique produit insuffisance, qualification ou abstention; une obligation non satisfaite reste visible; une donnée actuelle absente produit un statut explicite.
- Garde-fous: aucune conclusion complète avec obligation manquante; aucune lacune supprimée pour améliorer la réponse; aucune valeur de marché fabriquée.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-007 terminé.
- Présence des milestones amont dans master: M-007 et M-008 présents.
- Décisions manquantes: aucune pour les statuts RA existants; ADR requise si de nouveaux statuts publics remplacent les statuts documentaires publiés.
- Risques: confondre absence de contradiction et preuve suffisante; masquer les zones non documentées; surqualifier une réponse insuffisante.

## Tâches
### T-008 - Déclarer couverture insuffisante et lacunes
- But métier: informer l'utilisateur que la recherche approfondie reste partielle quand le corpus ne couvre pas le mandat.
- Portée DDD: politique `EvidenceCoveragePolicy`, `KnowledgeGap`, commandes `DeclareInsufficientEvidence` et `DeclareConflictingEvidence`, raisons publiques, statut `INSUFFICIENT_EVIDENCE` ou `REQUIRES_CURRENT_DATA`.
- Scénario BDD:
  - Given une obligation de couverture porte sur les coûts de transaction et aucune preuve admissible ne la couvre.
  - When RA évalue la couverture approfondie.
  - Then la lacune est enregistrée et la réponse ne peut pas être publiée comme entièrement supportée.
- Tests d'acceptation à écrire: `tests/m009/validate_insufficient_deep_coverage_acceptance.ps1`, qui échoue tant qu'une obligation manquante ne bloque pas le statut `SUPPORTED`.
- Tests unitaires à écrire: tests pour obligation manquante, raison publique absente, lacune dupliquée, donnée actuelle requise, contradiction bloquante prioritaire, obligation inconnue et statut `SUPPORTED` interdit.
- Implémentation attendue: étendre les politiques de couverture RA, enregistrer les `KnowledgeGap` M-009 dans `ResearchCase`, produire les événements d'insuffisance et exposer les lacunes dans le résultat public.
- Invariants et garde-fous: aucune couverture implicite; aucune preuve insuffisante promue en support; aucune lacune sans obligation; aucun statut public muet.
- Dépendances: T-005; T-007; `ResearchCase`; `KnowledgeGap`; `SupportStatus`.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_insufficient_deep_coverage_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_insufficient_deep_coverage_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m009): couvrir insuffisance recherche approfondie`
- Commit GREEN: `feat(m009): declarer insuffisance recherche approfondie`

