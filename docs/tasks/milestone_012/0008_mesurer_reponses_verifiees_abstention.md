# T-008 - Mesurer les réponses vérifiées et l'abstention

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, section `Évaluation des réponses` et métriques `Gouvernance des preuves` de la spécification v4.1.
- Objectif métier: mesurer si les réponses restent exactes, fidèles, citées et abstinentes quand les preuves sont insuffisantes, tout en publiant les métriques EG exigées par M-012.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: RA et EG évalués par M-012, avec KA et CV comme contextes associés.
- Objectif métier: évaluer exactitude, fidélité, précision des citations, complétude, abstention, contradictions, distinction source/déduction, absence de paramètres inventés, santé du registre de preuves et métriques RA normatives de support documentaire.
- Langage ubiquitaire: réponse vérifiée, assertion de réponse, citation, abstention, contradiction, source, déduction, paramètre inventé, statut documentaire, claim vérifié, claim rejeté, claim en revue, preuve directe, obligation de recherche, version obsolète réutilisée, groupe de dépendance, verdict, supersession.
- Invariants critiques: une assertion non supportée ne peut pas compter comme réponse correcte; une citation non ouvrable échoue; une abstention attendue non produite reste un échec; l'historique conversationnel ne devient pas preuve; une métrique EG ne peut pas compter une affirmation sans preuve directe comme vérifiée; une réponse réutilisant une version obsolète reste visible comme échec RA.
- Garde-fous: aucune correction par LLM juge sans preuve; aucun statut `SUPPORTED` pour assertion majeure non supportée; aucun paramètre de stratégie inventé accepté; aucun score agrégé qui masque contradictions, citations invalides, obligations de recherche manquantes ou versions obsolètes; aucune distribution EG ou RA sans dénominateur ni statut.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-007.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: aucune si l'évaluation utilise les contrats RA/EG publiés sans changer leur sens.
- Risques: juger la fluidité au lieu de la preuve; oublier les réponses qui doivent s'abstenir; compter une réponse plausible sans citation résolvable; publier une décision M-012 sans taux EG vérifié, rejeté, en revue ou sans distribution des verdicts.

## Tâches
### T-008 - Mesurer les réponses vérifiées et l'abstention
- But métier: rendre mesurable la qualité des réponses documentaires et approfondies.
- Portée DDD: `AnswerEvaluationCase`, `VerifiedAnswerBenchmark`, `EvidenceGovernanceBenchmark`, vérification des assertions, précision des citations, complétude, abstention attendue, contradiction, distinction source/déduction, paramètre inventé, taux `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` et `CONFLICTING_EVIDENCE`, nombre d'assertions non supportées retirées, couverture des obligations de recherche, part de réponses réutilisant une version obsolète, taux de claims vérifiés, rejetés et en revue, proportion d'affirmations sans preuve directe, distribution des verdicts, nombre de groupes de dépendance par sujet, taux de supersession et délai de vérification.
- Scénario BDD:
  - Given des questions d'évaluation avec preuves, contradictions ou insuffisances attendues.
  - When RA produit des réponses vérifiées et EG publie les états de claims associés au corpus pilote.
  - Then chaque réponse est mesurée sur support, citations, abstention et limites, et les métriques EG sont publiées sans traiter une réponse plausible comme preuve.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si une assertion non supportée est comptée comme correcte, si une citation non résolvable est acceptée, si une abstention attendue manque, si un paramètre inventé est ignoré, si les taux `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` ou `CONFLICTING_EVIDENCE` manquent, si les assertions non supportées retirées ne sont pas comptées, si la couverture des obligations de recherche manque, si les réponses réutilisant une version obsolète ne sont pas mesurées, si les taux de claims vérifiés/rejetés/en revue manquent, si la proportion d'affirmations sans preuve directe manque, si la distribution des verdicts manque ou si les groupes de dépendance ne sont pas comptés.
- Tests unitaires à écrire: tests de métriques pour assertion supportée, assertion partiellement supportée, preuve insuffisante, preuve conflictuelle, assertion non supportée retirée, obligation de recherche couverte, obligation de recherche manquante, réponse réutilisant une version obsolète, citation résolvable, citation cassée, contradiction explicitée, abstention correcte, abstention manquante, source/déduction confondues, paramètre inventé, claim vérifié sans preuve directe, distribution de verdicts, groupe de dépendance par sujet, supersession et délai de vérification.
- Implémentation attendue: créer les cas d'évaluation RA, le runner de réponses vérifiées, le benchmark EG, les calculateurs de métriques RA et EG, le rapport d'abstention, le rapport de gouvernance des preuves, le rapport de support documentaire RA et les contrôles de citations ouvrables.
- Invariants et garde-fous: aucune réponse sans statut documentaire; aucune preuve issue de l'historique brut; aucune métrique qui cache les assertions critiques, obligations de recherche manquantes ou versions obsolètes réutilisées; aucune acceptation d'une citation seulement textuelle sans résolution; aucune métrique RA ou EG dérivée d'un stockage interne hors port publié.
- Dépendances: T-007; `app/research_answering`; `app/evidence_governance`; `app/conversation`; `docs/specs/m006_claims_verifiables.md`; `docs/specs/m007_reponse_documentaire_verifiee.md`; `docs/specs/m008_conversation_produit.md`; `docs/specs/m009_recherche_approfondie_multi_sources.md`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir le benchmark reponses`
- Commit GREEN: `feat(m012): mesurer les reponses verifiees`
