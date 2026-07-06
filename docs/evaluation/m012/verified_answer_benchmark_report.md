# Rapport de benchmark réponses vérifiées RA M-012

## Scénario BDD

- Given des questions d'évaluation avec preuves, contradictions ou insuffisances attendues.
- When RA produit des réponses vérifiées, partielles, conflictuelles ou abstinentes sur le corpus pilote.
- Then chaque réponse est mesurée sur support documentaire, citations, exactitude, fidélité, complétude, abstention, contradictions, distinction source/déduction, paramètres inventés, obligations de recherche et versions obsolètes réutilisées.

## Contrat publié

- `AnswerEvaluationCase` consomme uniquement des observations publiques de réponse, de citation, d'assertion et d'obligation de recherche.
- `CitationMeasurement` exige un `SourceLocator` publié pour toute citation résolue; une citation textuelle sans résolution reste un échec mesuré.
- `AnswerAssertionMeasurement` ne compte jamais une assertion non supportée comme correcte.
- `VerifiedAnswerBenchmark` publie les quatre taux `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE` et `CONFLICTING_EVIDENCE` avec dénominateur.
- Une abstention attendue manquante, une contradiction non gérée, un paramètre inventé non rejeté ou une version obsolète réutilisée reste visible dans le résultat de cas.
- Une preuve issue de l'historique conversationnel brut est interdite.

## Métriques normatives RA

- `answer_support_status_rate`
- `answer_unsupported_assertion_removed_total`
- `answer_citation_precision`
- `answer_correct_abstention_rate`
- `answer_research_obligation_coverage`
- `answer_obsolete_version_reuse_rate`
- `answer_accuracy_score`
- `answer_fidelity_score`
- `answer_completeness_score`
- `answer_contradiction_management_rate`
- `answer_source_deduction_distinction_rate`
- `answer_invented_parameter_rejection_rate`

ADR: non requise; T-008 applique ADR-010 et DDD-ADR-007 sans modifier leur sens.
