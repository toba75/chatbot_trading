# M-007 - Réponse documentaire vérifiée

## Statut

- Milestone: M-007 - Réponse documentaire vérifiée.
- ADR consultées: ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007, DDD-ADR-008.
- ADR: non requise, car M-007 applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given un brouillon contenant une assertion factuelle importante.
- When la spécification M-007 est publiée.
- Then chaque comportement de réponse nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission RA

RA transforme une question autonome et un `ResearchMandate` explicite en réponse documentaire vérifiée, qualifiée ou abstinente. RA planifie la recherche, demande des preuves candidates à KA, demande des claims vérifiés à EG, scelle un `EvidenceSet`, analyse les contradictions et lacunes, rédige un brouillon, extrait les `AnswerAssertion`, évalue leur support et publie seulement une version de réponse conforme.

Une réponse SUPPORTED exige que chaque assertion importante conservée soit supportée. Le jeu de preuves publié est figé. Toute Citation reste ouvrable jusqu'au SourceLocator. RA consomme KnowledgeSearch sans accès direct à Qdrant et RA consomme VerifiedClaimCatalog sans lecture du registre EG interne. Le LLM propose un brouillon; la politique RA décide le SupportStatus. Aucune valeur de marché n'est inventée.

Les garde-fous de mission sont explicites: aucune assertion factuelle non supportée n'est publiée comme connaissance; aucun statut implicite n'est attribué; aucun prompt, brouillon ou détail de stockage ne fait partie du contrat public; toute absence de données actuelles autorisées produit `REQUIRES_CURRENT_DATA` ou `CURRENT_DATA_REQUIRED`.

## Contexte DDD

- Domaine: recherche et réponse vérifiée.
- Bounded context: RA.
- Objectif métier: produire une réponse citée, qualifiée, conflictuelle, insuffisamment documentée ou abstinente sans masquer le défaut de preuve.
- Intégrations: RA consomme `KnowledgeSearch` côté KA, `VerifiedClaimCatalog` côté EG, `SourceLocator` pour l'ouverture des citations, et publie `VerifiedResearchOutcome` vers CV et SD.
- Garde-fous: aucune dépendance aux stockages internes SP, KA ou EG; aucune décision métier dérivée d'un score seul; aucune sortie de modèle publiée sans politique RA.

## Langage ubiquitaire RA

| Terme | Sens M-007 |
|---|---|
| ResearchCase | Agrégat RA qui fige la question autonome, le mandat, les obligations de couverture, le jeu de preuves, les contradictions, les lacunes et l'issue de recherche. |
| Answer | Agrégat RA qui porte brouillon, assertions, citations, support documentaire et version finale immuable. |
| ResearchMandate | Objet métier qui définit univers autorisé, horizon, exigences de données, exclusions, langue et niveau de détail. |
| EvidenceSet | Jeu de preuves RA scellé, versionné et rattaché à un ResearchCase avant publication. |
| AnswerAssertion | Assertion atomique extraite du brouillon et évaluée séparément. |
| Citation | Référence ouvrable contenant SourceLocator, hash de span et lien vers la preuve ou le claim utilisé. |
| ContradictionAssessment | Classement explicite d'une opposition documentaire selon portée, horizon, univers et conditions. |
| KnowledgeGap | Lacune documentaire empêchant une conclusion supportée ou imposant une qualification. |
| SupportStatus | Résultat documentaire publié parmi SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, CONFLICTING_EVIDENCE et REQUIRES_CURRENT_DATA. |
| AbstentionReason | Raison publique d'abstention, notamment données actuelles requises, preuves insuffisantes, conflit non résolu ou mandat interdit. |
| VerifiedClaimRef | Référence EG publiée vers une version de claim vérifiée. |
| VerifiedResearchOutcome | Contrat versionné publié par RA pour exposer la réponse, le statut, les claims, contradictions, lacunes et horodatage. |

## Agrégats RA

| Agrégat | Responsabilité M-007 | Invariants | Événements |
|---|---|---|---|
| ResearchCase | Porter la question autonome, le ResearchMandate, le plan, les obligations de couverture, l'EvidenceSet et les diagnostics de recherche. | Question et mandat obligatoires; EvidenceSet scellé avant publication; lacunes et contradictions pertinentes conservées. | ResearchCaseOpened; ResearchPlanCreated; EvidenceCollectionCompleted; EvidenceSetSealed; ContradictionDetected; KnowledgeGapRecorded; ResearchEvidenceFoundInsufficient; ResearchEvidenceFoundConflicting |
| Answer | Porter le brouillon, les AnswerAssertion, les Citation, le SupportStatus et la version finale immuable. | SUPPORTED interdit si une assertion importante conservée n'est pas supportée; Citation ouvrable obligatoire; version finale immuable. | AnswerDrafted; AnswerAssertionsExtracted; AnswerSupportEvaluated; AnswerVerified; AnswerPartiallySupported; AnswerPublicationBlocked; AnswerAbstained; AnswerSuperseded |

## Objets-valeur RA

| Objet-valeur | Sens M-007 | Invariants |
|---|---|---|
| ResolvedQuestion | Question autonome reçue par RA depuis CV ou API directe. | Obligatoire et stable pour le ResearchCase. |
| ResearchMandate | Contraintes métier autorisées pour la réponse. | Aucun champ requis par une politique ne peut être absent. |
| ResearchMode | Mode documentaire simple ou approfondi demandé. | M-007 couvre la réponse documentaire simple; M-009 couvre l'approfondi multi-sources. |
| EvidenceSet | Ensemble des preuves retenues pour une réponse. | Scellé, versionné et non modifiable après publication. |
| EvidenceSetVersion | Version du jeu de preuves publié. | Toute modification crée une nouvelle version. |
| AnswerAssertion | Proposition atomique extraite du brouillon. | Toute assertion importante est évaluée et reliée à support, retrait, qualification ou abstention. |
| AssertionOrigin | Origine de l'assertion: source, déduction ou choix de conception. | Ne peut pas être implicite. |
| Citation | Référence ouvrable vers SourceLocator et preuve utilisée. | Doit ouvrir la page et le fragment source. |
| ContradictionAssessment | Diagnostic de contradiction ou de non-comparabilité. | Conserve horizon, univers, métrique et condition. |
| KnowledgeGap | Lacune documentaire enregistrée. | Produit qualification, insuffisance ou abstention explicite. |
| SupportStatus | Statut documentaire global de la réponse. | Décidé par politique RA, jamais par score isolé. |
| AbstentionReason | Raison publique d'abstention. | Obligatoire quand aucune réponse supportée ou qualifiée n'est publiable. |

## Politiques normatives M-007

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| ResearchMandatePolicy | Refuse une recherche sans mandat explicite ou hors mandat. | ResearchCase ouvert seulement avec question autonome et ResearchMandate. | ADR-010 |
| EvidenceSetSealingPolicy | Fige les preuves retenues avant publication. | EvidenceSet versionné et non modifiable une fois publié. | DDD-ADR-003; DDD-ADR-008 |
| AnswerAssertionExtractionPolicy | Décompose le brouillon en AnswerAssertion vérifiables. | Une assertion importante ne reste pas implicite dans le texte final. | DDD-ADR-005; DDD-ADR-007 |
| AnswerSupportPolicy | Décide SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, CONFLICTING_EVIDENCE ou REQUIRES_CURRENT_DATA. | SUPPORTED exige support pour chaque assertion importante conservée. | ADR-006; DDD-ADR-005; DDD-ADR-007 |
| CitationIntegrityPolicy | Vérifie que chaque Citation ouvre un SourceLocator résoluble. | Une citation non ouvrable bloque la publication supportée. | DDD-ADR-003 |
| ContradictionAssessmentPolicy | Classe contradictions, horizons différents et incompatibilités de portée. | Une contradiction pertinente n'est pas supprimée pour simplifier la conclusion. | DDD-ADR-005 |
| KnowledgeGapPolicy | Enregistre les lacunes qui limitent la réponse. | Une lacune critique produit insuffisance, qualification ou abstention. | ADR-006; DDD-ADR-005 |
| AbstentionPolicy | Publie une abstention quand les preuves ou données autorisées manquent. | L'abstention porte une AbstentionReason publique. | DDD-ADR-007 |
| CurrentDataRequirementPolicy | Détecte les demandes de données actuelles non autorisées. | Aucun prix ou niveau de marché récent n'est fabriqué. | DDD-ADR-007 |

## Machine d'états M-007

| État | Portée | Sens M-007 | Transition autorisée |
|---|---|---|---|
| CREATED | ResearchCase | Question autonome et ResearchMandate enregistrés. | Vers PLANNED. |
| PLANNED | ResearchCase | Obligations de couverture et recherche documentaire planifiées. | Vers COLLECTING_EVIDENCE. |
| COLLECTING_EVIDENCE | ResearchCase | Preuves candidates KA et claims EG demandés. | Vers EVIDENCE_ASSEMBLED, INSUFFICIENT_EVIDENCE ou CONFLICTING_EVIDENCE. |
| EVIDENCE_ASSEMBLED | ResearchCase | EvidenceSet assemblé et prêt à sceller. | Vers SYNTHESIZING. |
| SYNTHESIZING | ResearchCase | Brouillon produit comme proposition non publiée. | Vers VERIFYING. |
| VERIFYING | ResearchCase | Assertions, citations, contradictions et lacunes évaluées. | Vers COMPLETED, INSUFFICIENT_EVIDENCE ou CONFLICTING_EVIDENCE. |
| COMPLETED | ResearchCase | Issue RA publiée. | Terminal pour cette version. |
| INSUFFICIENT_EVIDENCE | ResearchCase | Couverture ou preuves insuffisantes. | Terminal pour cette version. |
| CONFLICTING_EVIDENCE | ResearchCase | Contradiction non résolue empêchant une réponse supportée. | Terminal pour cette version. |
| DRAFT | Answer | Brouillon révisable non public. | Vers ASSERTIONS_EXTRACTED. |
| ASSERTIONS_EXTRACTED | Answer | AnswerAssertion atomiques extraites. | Vers SUPPORT_EVALUATED. |
| SUPPORT_EVALUATED | Answer | Support, citations, contradictions et lacunes décidés. | Vers VERIFIED, PARTIALLY_SUPPORTED, INSUFFICIENT_EVIDENCE, CONFLICTING_EVIDENCE, ABSTAINED ou REJECTED. |
| VERIFIED | Answer | Réponse SUPPORTED publiée en version immuable. | Vers AnswerSuperseded par nouvelle version. |
| PARTIALLY_SUPPORTED | Answer | Réponse publiée avec qualifications explicites. | Vers AnswerSuperseded par nouvelle version. |
| ABSTAINED | Answer | Abstention REQUIRES_CURRENT_DATA publiée avec provenance documentaire. | Terminal pour cette version ou vers AnswerSuperseded. |
| REJECTED | Answer | Brouillon non publiable. | Terminal pour ce brouillon. |

## Ports et adaptateurs RA

| Port | Responsabilité | Interdiction |
|---|---|---|
| KnowledgeSearch | Obtenir des preuves candidates KA par contrat publié. | Aucun accès à Qdrant, collection, point id ou profil de stockage. |
| VerifiedClaimCatalog | Lire des VerifiedClaimRef et preuves publiques EG. | Aucune lecture du registre EG interne ni mutation de claim. |
| EvidenceAssembler | Assembler et diversifier les preuves retenues. | Ne scelle pas un EvidenceSet incomplet ou non traçable. |
| ContradictionAnalyzer | Proposer des ContradictionAssessment structurés. | Ne généralise pas une contradiction hors portée comparable. |
| AnswerGenerator | Produire un brouillon structuré. | Ne publie pas, ne décide pas le SupportStatus et ne masque pas les preuves manquantes. |
| AnswerAssertionExtractor | Extraire les AnswerAssertion du brouillon. | N'ignore pas une assertion factuelle importante. |
| AnswerVerifier | Proposer des signaux de support. | Ne modifie pas l'état métier sans AnswerSupportPolicy. |
| CitationResolver | Vérifier l'ouverture des Citation vers SourceLocator. | Ne remplace pas un SourceLocator invalide par un chemin local. |
| CurrentDataAuthorization | Déterminer si une donnée actuelle est autorisée. | Ne fabrique pas de valeur de marché. |
| ResearchCaseRepository | Persister ResearchCase et événements RA. | Ne persiste pas de stockage KA, EG ou SP interne. |
| AnswerRepository | Persister Answer et versions publiées. | Ne modifie jamais une version finale immuable. |

## Événements RA

| Événement | Déclencheur | Payload publié |
|---|---|---|
| ResearchCaseOpened | Ouverture d'un ResearchCase. | research_case_id; resolved_question_hash; mandate_hash; requested_by_context |
| ResearchPlanCreated | Obligations de couverture définies. | research_case_id; coverage_obligations; policy_version |
| EvidenceCollectionCompleted | Collecte documentaire terminée. | research_case_id; candidate_count; verified_claim_ref_count |
| EvidenceSetSealed | EvidenceSet figé. | research_case_id; evidence_set_id; evidence_set_version; evidence_hash |
| ContradictionDetected | Contradiction ou non-comparabilité identifiée. | research_case_id; contradiction_type; affected_claim_refs |
| KnowledgeGapRecorded | Lacune documentaire enregistrée. | research_case_id; gap_type; affected_obligation |
| AnswerDrafted | Brouillon généré. | answer_id; research_case_id; draft_hash; model_provenance |
| AnswerAssertionsExtracted | Assertions extraites du brouillon. | answer_id; assertion_count; extractor_version |
| AnswerSupportEvaluated | Support documentaire décidé. | answer_id; support_status; unsupported_assertion_count; policy_version |
| AnswerVerified | Réponse SUPPORTED publiée. | answer_id; answer_version; evidence_set_version; citation_count |
| AnswerPartiallySupported | Réponse qualifiée publiée. | answer_id; answer_version; knowledge_gap_count; citation_count |
| AnswerPublicationBlocked | Réponse bloquée par preuves insuffisantes ou conflit. | answer_id; answer_version; support_status; reason_code; citation_count |
| ResearchEvidenceFoundInsufficient | Preuves insuffisantes. | research_case_id; missing_obligations; reason_codes |
| ResearchEvidenceFoundConflicting | Conflit non résolu. | research_case_id; contradiction_ids; reason_codes |
| AnswerAbstained | Abstention RA publiée. | answer_id; abstention_reason; support_status |
| AnswerSuperseded | Réponse remplacée explicitement. | old_answer_ref; new_answer_ref; supersession_reason |

## API publique RA

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/answer | 200 ANSWER_PUBLISHED quand une réponse supportée, qualifiée, conflictuelle, insuffisante ou abstinente est publiée. | 400 HTTP_REQUEST_INVALID; 403 ANSWER_CONTEXT_FORBIDDEN; 404 ENDPOINT_NOT_FOUND; 422 RESEARCH_MANDATE_REQUIRED; 409 EVIDENCE_SET_NOT_SEALED; 422 ANSWER_ASSERTION_UNSUPPORTED; 422 ANSWER_CITATION_UNRESOLVABLE; 409 ANSWER_CONFLICT_UNRESOLVED; 422 INSUFFICIENT_EVIDENCE; 422 CURRENT_DATA_REQUIRED; 409 ANSWER_PUBLICATION_FORBIDDEN; 422 RA_POLICY_MISSING. | schema_version; research_case_id; answer_id; support_status; answer_text; citations; claim_refs; unresolved_conflicts; knowledge_gaps; abstention_reason; completed_at. |

### Corps de requête publics

| Endpoint | Champs acceptés | Champs interdits |
|---|---|---|
| POST /v1/answer | resolved_question; research_mandate; requested_mode; idempotency_key; occurred_at | qdrant_collection; qdrant_point_id; eg_registry_table; sp_table; prompt_override; support_status_override; draft_text_as_final |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête RA invalide. |
| ENDPOINT_NOT_FOUND | 404 | Endpoint RA absent pour la route demandée. |
| ANSWER_CONTEXT_FORBIDDEN | 403 | Contexte authentifié non autorisé à publier une réponse RA. |
| RESEARCH_MANDATE_REQUIRED | 422 | Mandat de recherche absent ou incomplet. |
| RESEARCH_CASE_NOT_FOUND | 404 | Cas de recherche inconnu ou version absente. |
| EVIDENCE_SET_NOT_SEALED | 409 | Publication demandée avant scellement du jeu de preuves. |
| ANSWER_ASSERTION_UNSUPPORTED | 422 | Assertion importante conservée sans support admissible. |
| ANSWER_CITATION_UNRESOLVABLE | 422 | Citation absente, non ouvrable ou incohérente avec SourceLocator. |
| ANSWER_CONFLICT_UNRESOLVED | 409 | Contradiction pertinente non résolue empêche une réponse supportée. |
| INSUFFICIENT_EVIDENCE | 422 | Preuves insuffisantes pour répondre dans le mandat. |
| CURRENT_DATA_REQUIRED | 422 | La question requiert des données actuelles non autorisées. |
| ANSWER_PUBLICATION_FORBIDDEN | 409 | L'état courant interdit la publication publique. |
| RA_POLICY_MISSING | 422 | Version de politique RA absente pour décider le support. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| answer_support_status_total | Métrique | Compte les SupportStatus publiés par politique et mode. |
| answer_unsupported_assertions_removed_total | Métrique | Compte les assertions retirées ou qualifiées avant publication. |
| answer_citation_resolution_failed_total | Métrique | Compte les Citation non ouvrables sans exposer le texte source complet. |
| answer_abstention_total | Métrique | Compte les abstentions par AbstentionReason. |
| research_coverage_obligation_met_total | Métrique | Compte les obligations de couverture satisfaites. |
| answer_conflict_detected_total | Métrique | Compte les contradictions conservées ou bloquantes. |
| answer_knowledge_gap_total | Métrique | Compte les KnowledgeGap par type. |
| answer_evidence_set_sealed_total | Métrique | Compte les EvidenceSet scellés par version de politique. |
| answer_model_draft_total | Trace | Compte les brouillons de modèle par hash sans payload complet. |

## Comportements vérifiables M-007

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| RA-001 - Spécification exécutable M-007 | La spécification nomme mission RA, agrégats, objets-valeur, politiques, états, ports, événements, API, erreurs, métriques, exclusions et garde-fous. | Given un brouillon contenant une assertion factuelle importante; When la spécification M-007 est publiée; Then elle est validée par commande uv run --locked gate
| RA-002 - Cas de recherche avec mandat explicite | Un ResearchCase possède question autonome et ResearchMandate explicite. | Given une question autonome et un mandat explicite; When RA ouvre un ResearchCase; Then le cas est CREATED avec mandat figé. | T-003 | ADR-010 | uv run --locked gate
| RA-003 - Jeu de preuves scellé | EvidenceSet est scellé avant publication et ne change pas après réponse publiée. | Given des preuves candidates et claims vérifiés; When RA scelle le jeu de preuves; Then la version d'EvidenceSet est figée et rattachée à l'Answer. | T-004 | DDD-ADR-003; DDD-ADR-008 | uv run --locked gate
| RA-004 - Contradictions et lacunes classées | ContradictionAssessment et KnowledgeGap conservent portée et conditions. | Given deux claims opposés sur des horizons différents; When RA analyse les contradictions; Then la relation est qualifiée sans contradiction générale abusive. | T-005 | DDD-ADR-005 | uv run --locked gate
| RA-005 - Assertions de réponse extraites | Toute assertion importante du brouillon est évaluée. | Given un brouillon contenant une assertion factuelle importante; When RA extrait les assertions; Then chaque AnswerAssertion est reliée à origine, support attendu ou retrait. | T-006 | DDD-ADR-005; DDD-ADR-007 | uv run --locked gate
| RA-006 - Support et citations évalués | SUPPORTED exige support et Citation ouvrable pour chaque assertion importante conservée. | Given une assertion non supportée et une citation absente; When RA évalue le support; Then ANSWER_ASSERTION_UNSUPPORTED ou ANSWER_CITATION_UNRESOLVABLE bloque SUPPORTED. | T-007 | ADR-006; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007 | uv run --locked gate
| RA-007 - Abstention données actuelles | Une donnée actuelle requise mais non autorisée produit abstention explicite. | Given une question nécessitant des prix récents; When aucune donnée actuelle n'est autorisée; Then REQUIRES_CURRENT_DATA est publié sans niveau de marché fabriqué. | T-008 | DDD-ADR-007 | uv run --locked gate
| RA-008 - Commande publique de réponse documentaire | POST /v1/answer expose le contrat RA sans stockage interne ni prompt public. | Given un ResearchMandate valide; When POST /v1/answer est appelé; Then la réponse publique contient VerifiedResearchOutcome, SupportStatus, citations, conflits et lacunes. | T-009 | ADR-010; DDD-ADR-003; DDD-ADR-005 | uv run --locked gate
| RA-009 - Traçabilité et métriques M-007 | Chaque exigence M-007 possède test, commande, ADR et métrique sans payload documentaire complet. | Given les preuves M-007; When les gates s'exécutent; Then traceability, test, lint et validate_m007_specification sont enrôlés. | T-010 | ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-008 | uv run --locked gate

## Commandes de validation

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-007

- M-007 ne livre pas la conversation produit M-008 ni la résolution d'historique conversationnel.
- M-007 ne livre pas la recherche approfondie multi-sources M-009.
- M-007 ne change pas le contrat `VerifiedResearchOutcome` publié par M-001.
- M-007 ne décide pas une politique durable de versioning automatique des réponses réutilisées.
- M-007 ne publie aucun prompt, brouillon, collection Qdrant, table EG, table SP ou détail de stockage comme contrat public.
- M-007 ne modifie pas la signification des ADR acceptées; ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008 sont appliquées telles quelles.
