# T-007 - Évaluer le support et publier les citations de réponse

## Milestone
- Nom: M-007 - Réponse documentaire vérifiée.
- Source: plan M-007 et spécification v4.1, section RA `AnswerSupportPolicy`, `CitationIntegrityPolicy`, `AnswerFreshnessPolicy`, statuts de réponse et contrat `VerifiedResearchOutcome`.
- Objectif métier: publier une réponse seulement si ses assertions importantes sont supportées, qualifiées ou retirées.

## Contexte DDD
- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: transformer un brouillon vérifié en réponse finale avec statut documentaire explicite et citations ouvrables.
- Langage ubiquitaire: `AnswerSupportPolicy`, `CitationIntegrityPolicy`, `AnswerFreshnessPolicy`, `SupportStatus`, `VerifiedAnswerVersion`, `VerifiedResearchOutcome`, `EvaluateAnswerSupport`, `PublishVerifiedAnswer`, `SupersedeAnswer`.
- Invariants critiques: `SUPPORTED` exige que chaque assertion importante conservée ait un support admissible; chaque citation est ouvrable; une version publiée est immuable; une réponse réutilisée est revalidée si ses sources ou politiques sont obsolètes.
- Garde-fous: aucune assertion non supportée publiée comme fait; aucun support par score seul; aucun lien de citation cassé; aucun conflit masqué.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-004 et T-006 terminés; T-005 terminé pour les cas conflictuels.
- Présence des milestones amont dans master: M-006 présent.
- Décisions manquantes: aucune si `VerifiedResearchOutcome` existant suffit; ADR requise si le contrat public RA vers SD est modifié.
- Risques: statut global trop optimiste; suppression silencieuse d'une assertion importante; réponse publiée sans version immuable; citation non résoluble; ancienne réponse réutilisée sans revalidation après obsolescence de source ou de politique.

## Tâches
### T-007 - Évaluer le support et publier les citations de réponse
- But métier: garantir que la réponse finale n'élève jamais une hypothèse au rang de connaissance.
- Portée DDD: politique `AnswerSupportPolicy`, politique `CitationIntegrityPolicy`, politique `AnswerFreshnessPolicy`, publication `VerifiedAnswerVersion`, production du contrat `VerifiedResearchOutcome`, commande `SupersedeAnswer`, événements `AnswerSupportEvaluated`, `AnswerVerified`, `AnswerPartiallySupported` et `AnswerSuperseded`.
- Scénario BDD:
  - Given un brouillon contient une assertion factuelle importante sans preuve admissible.
  - When RA évalue le support de la réponse.
  - Then l'assertion est retirée ou reformulée comme incertaine, et la réponse ne reçoit pas le statut `SUPPORTED` tant que le défaut subsiste.
- Tests d'acceptation à écrire: `tests/m007/validate_answer_support_acceptance.ps1`, qui échoue tant que RA peut publier `SUPPORTED` avec une assertion importante non supportée.
- Tests unitaires à écrire: tests pour assertion non supportée, citation non ouvrable, conflit non résolu, preuve indirecte seule, statut `PARTIALLY_SUPPORTED`, version publiée immuable, source obsolète, politique de support obsolète, `AnswerSuperseded`, `VerifiedResearchOutcome` invalide et suppression silencieuse d'assertion sans trace.
- Implémentation attendue: ajouter l'évaluateur de support, le vérificateur de citations, la publication immuable de réponse, la conversion vers `VerifiedResearchOutcome`, les raisons de qualification, la politique de fraîcheur et la supersession explicite d'une réponse publiée devenue obsolète.
- Invariants et garde-fous: aucune citation cassée; aucun statut par défaut; aucune preuve indirecte seule pour `SUPPORTED`; aucune mutation de version publiée; aucune omission de contradiction pertinente; aucune réutilisation de réponse obsolète sans revalidation ou supersession explicite.
- Dépendances: T-004; T-005; T-006; contrat `VerifiedResearchOutcome` M-001; claims EG M-006.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_support_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m007\validate_answer_support_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_architecture_boundaries.ps1 -AppRoot .\app -ContextRegistryPath .\app\context_registry.json -SpecificationPath .\docs\specs\m001_frontieres_ddd_contrats_publies.md`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m007): couvrir support citations reponse`
- Commit GREEN: `feat(m007): evaluer support citations reponse`
