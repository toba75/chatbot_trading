# M-009 - Recherche approfondie multi-sources

## Statut

- Milestone: M-009.
- Tâche de publication: T-002 - Publier la spécification de recherche approfondie multi-sources.
- Bounded context propriétaire: RA.
- Contextes intégrés: KA pour les preuves candidates, EG pour les claims vérifiés, CV pour la consommation conversationnelle.
- ADR applicables: ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008.
- ADR: non requise pour T-002, qui applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given la mission M-009 est d'analyser plusieurs sources sans effacer nuances, limites et contradictions.
- When la spécification de recherche approfondie est publiée.
- Then chaque comportement M-009 nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission RA approfondie

RA étend le mode `ResearchMode` avec `RECHERCHE_APPROFONDIE` pour transformer une question autonome et un `ResearchMandate` explicite en recherche approfondie multi-sources. Une recherche approfondie possède un plan et des obligations de couverture. Les versions de projection et de claims sont enregistrées. Une contradiction pertinente n'est pas omise. La fréquence de citation ne devient pas consensus. Source, déduction et choix de conception restent distingués.

RA consomme KnowledgeSearch sans accès direct à Qdrant et RA consomme VerifiedClaimCatalog sans lecture du registre EG interne. RA conserve les preuves favorables, preuves défavorables, groupes de dépendance, contradictions conditionnelles et lacunes documentaires avant toute synthèse. Aucune synthèse SUPPORTED n'est publiée sans couverture minimale. Aucun paramètre de stratégie n'est inventé et aucune valeur de marché actuelle n'est fabriquée.

Le contrat public M-009 définit le mode approfondi, le plan de recherche, les obligations de couverture, la diversification des recherches, les dépendances EG, les contradictions, les lacunes, la synthèse multi-sources, l'endpoint `POST /v1/research/deep`, les erreurs publiques, les métriques et les exclusions vers SD et EX.

## Contexte DDD

- Domaine: recherche et réponse vérifiée approfondie.
- Bounded context: RA, avec intégration EG et consommation par CV.
- Objectif métier: couvrir, comparer et synthétiser plusieurs sources sans effacer conditions, limites, dépendances ou contradictions.
- Intégrations: RA consomme `KnowledgeSearch`, `VerifiedClaimCatalog`, `ProjectionVersionCatalog` et `SourceLocator`; RA publie un résultat vérifié ou qualifié vers CV.
- Garde-fous: aucun mandat implicite; aucun accès direct aux stockages internes SP, KA ou EG; aucun consensus dérivé du nombre brut de mentions; aucune sortie de modèle publiée sans décision de politique RA.

## Langage ubiquitaire RA approfondie

| Terme | Sens M-009 |
|---|---|
| ResearchCase | Agrégat RA qui porte le mode `RECHERCHE_APPROFONDIE`, le plan, les obligations, les preuves, les contradictions, les lacunes et l'issue. |
| Answer | Agrégat RA qui porte la synthèse publiée, le statut de support, les citations et les qualifications. |
| ResearchMandate | Mandat explicite qui borne l'univers, l'horizon, les sources autorisées, les exclusions, la langue et le niveau de détail. |
| ResearchMode | Objet-valeur qui contient le mode `RECHERCHE_APPROFONDIE` sans fallback vers le mode documentaire simple. |
| DeepResearchPlan | Plan ordonné de sous-questions, requêtes, obligations de couverture et critères d'arrêt. |
| ResearchSubQuestion | Sous-question autonome rattachée à une obligation de couverture. |
| CoverageObligation | Obligation vérifiable de couvrir un angle, une période, un univers, une méthode, une preuve favorable ou une preuve défavorable. |
| EvidencePolarity | Qualification favorable, défavorable, neutre ou non comparable d'une preuve par rapport à la sous-question. |
| IndependentEvidenceGroup | Groupe de preuves dont l'indépendance est justifiée sans confondre répétition documentaire et confirmation indépendante. |
| VerifiedClaimRef | Référence EG publiée vers une version de claim vérifiée. |
| ProjectionVersionRef | Référence de version KA utilisée pour tracer l'état de projection consulté. |
| ConditionalContradiction | Contradiction qualifiée par conditions, horizon, univers, métrique, coûts ou dépendances. |
| DocumentaryGap | Lacune documentaire empêchant une conclusion supportée ou imposant une qualification. |
| MultiSourceSynthesis | Synthèse qui distingue source, déduction, choix de conception, conditions, limites et contradictions. |
| DeepResearchSupportStatus | Statut publié parmi SUPPORTED, PARTIALLY_SUPPORTED, INSUFFICIENT_COVERAGE, CONFLICTING_EVIDENCE et REQUIRES_CURRENT_DATA. |

## Agrégats RA approfondie

| Agrégat | Responsabilité M-009 | Invariants | Événements |
|---|---|---|---|
| ResearchCase | Porter la question autonome, le ResearchMandate, le ResearchMode `RECHERCHE_APPROFONDIE`, le DeepResearchPlan, les CoverageObligation, les versions consultées, les preuves et les diagnostics. | Mandat explicite obligatoire; plan obligatoire avant collecte; obligation de couverture tracée avant synthèse; contradiction pertinente conservée. | DeepResearchRequested; DeepResearchPlanCreated; CoverageObligationDeclared; DeepResearchEvidenceCollected; ClaimDependencyGroupResolved; ConditionalContradictionDetected; DocumentaryGapRecorded; DeepResearchCoverageInsufficient |
| Answer | Porter la MultiSourceSynthesis, les citations, le DeepResearchSupportStatus et la version finale immuable. | SUPPORTED interdit si couverture minimale absente; citations ouvrables obligatoires; fréquence de citation jamais traitée comme consensus; source, déduction et choix de conception séparés. | MultiSourceSynthesisDrafted; DeepResearchSupportEvaluated; DeepResearchCompleted; DeepResearchPublicationBlocked |

## Objets-valeur RA approfondie

| Objet-valeur | Sens M-009 | Invariants |
|---|---|---|
| ResearchMandate | Mandat explicite de recherche approfondie. | Obligatoire; bornes et exclusions enregistrées; aucune recherche approfondie implicite. |
| ResearchMode | Mode demandé ou sélectionné par CV. | `RECHERCHE_APPROFONDIE` requis pour `POST /v1/research/deep`; aucun fallback silencieux. |
| DeepResearchPlan | Plan ordonné de sous-questions et d'obligations. | Au moins une ResearchSubQuestion et une CoverageObligation avant collecte. |
| ResearchSubQuestion | Question autonome de couverture. | Rattachée à une obligation et à un objectif de preuve. |
| CoverageObligation | Unité vérifiable de couverture documentaire. | Statut explicite: couverte, insuffisante ou hors mandat. |
| EvidencePolarity | Sens d'une preuve par rapport à une obligation. | Favorable, défavorable, neutre ou non comparable; jamais implicite. |
| IndependentEvidenceGroup | Groupe de dépendance de preuves ou claims. | Indépendance justifiée; répétition d'une étude non comptée deux fois. |
| ProjectionVersionRef | Version KA consultée pour la recherche. | Version obligatoire dans la trace de recherche. |
| VerifiedClaimVersionRef | Version EG consultée pour la vérification. | Claim id et version obligatoires. |
| ConditionalContradiction | Contradiction qualifiée. | Conditions, horizon, univers, métrique et dépendance conservés. |
| DocumentaryGap | Lacune documentaire enregistrée. | Reliée à une CoverageObligation et à une raison publique. |
| MultiSourceSynthesis | Synthèse approfondie publiée. | Distingue source, déduction et choix de conception; conserve limites et contradictions. |
| DeepResearchSupportStatus | Statut de support approfondi. | Décidé par politique RA, jamais par score ou fréquence de citation. |

## Politiques normatives M-009

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| DeepResearchMandatePolicy | Exige un ResearchMandate explicite pour toute recherche approfondie. | Aucune recherche approfondie sans mandat explicite. | ADR-010; DDD-ADR-007 |
| ResearchModePolicy | Valide `RECHERCHE_APPROFONDIE` comme mode RA explicite. | Aucun fallback vers CHAT_DOCUMENTAIRE ou réponse rapide. | ADR-010; DDD-ADR-007 |
| DeepResearchPlanningPolicy | Produit un DeepResearchPlan avant collecte. | Plan et obligations obligatoires avant toute synthèse. | ADR-006; DDD-ADR-005 |
| CoverageObligationPolicy | Évalue chaque CoverageObligation. | Une obligation non couverte bloque SUPPORTED ou impose qualification. | ADR-006; DDD-ADR-003; DDD-ADR-005 |
| SourceDiversificationPolicy | Diversifie les requêtes, sources, horizons et polarités de preuve. | La fréquence de citation ne devient pas consensus. | ADR-006; DDD-ADR-005 |
| VerifiedClaimDependencyPolicy | Résout les VerifiedClaimVersionRef et IndependentEvidenceGroup depuis EG publié. | Les versions de claims et groupes de dépendance sont enregistrés. | ADR-006; DDD-ADR-005; DDD-ADR-008 |
| ConditionalContradictionPolicy | Classe les contradictions selon conditions, horizon, univers, métrique et dépendances. | Une contradiction pertinente n'est pas omise. | DDD-ADR-005; DDD-ADR-007 |
| DeepResearchSupportPolicy | Décide DeepResearchSupportStatus depuis couverture, preuves, claims, contradictions et lacunes. | Aucun score probabiliste ni nombre de mentions ne décide le support. | ADR-006; DDD-ADR-005; DDD-ADR-007 |
| MultiSourceSynthesisPolicy | Publie une synthèse qui conserve sources, déductions, choix de conception, conditions et limites. | Source, déduction et choix de conception restent distingués. | DDD-ADR-003; DDD-ADR-007 |
| DeepResearchObservabilityPolicy | Publie métriques et traces sans payload documentaire complet. | Les versions de projection, claims et politiques sont auditables. | ADR-010; DDD-ADR-008 |

## Machine d'états M-009

| État | Portée | Sens M-009 | Transition autorisée |
|---|---|---|---|
| DEEP_REQUESTED | ResearchCase | Requête approfondie reçue avec mandat explicite. | Vers DEEP_PLANNED ou REJECTED. |
| DEEP_PLANNED | ResearchCase | DeepResearchPlan créé. | Vers COVERAGE_OBLIGATIONS_DECLARED. |
| COVERAGE_OBLIGATIONS_DECLARED | ResearchCase | Obligations de couverture figées pour cette version. | Vers COLLECTING_MULTI_QUERY_EVIDENCE. |
| COLLECTING_MULTI_QUERY_EVIDENCE | ResearchCase | Requêtes KA et lectures EG publiées exécutées. | Vers EVIDENCE_DIVERSIFIED, COVERAGE_INSUFFICIENT ou REJECTED. |
| EVIDENCE_DIVERSIFIED | ResearchCase | Preuves favorables et défavorables diversifiées. | Vers CLAIM_DEPENDENCIES_RESOLVED. |
| CLAIM_DEPENDENCIES_RESOLVED | ResearchCase | Groupes de dépendance et versions EG enregistrés. | Vers CONTRADICTIONS_CLASSIFIED. |
| CONTRADICTIONS_CLASSIFIED | ResearchCase | Contradictions et non-comparabilités classées. | Vers SYNTHESIZING_MULTI_SOURCE ou COVERAGE_INSUFFICIENT. |
| COVERAGE_INSUFFICIENT | ResearchCase | Couverture minimale non atteinte. | Terminal pour cette version ou vers DeepResearchPlanCreated par nouvelle version. |
| SYNTHESIZING_MULTI_SOURCE | ResearchCase | Synthèse proposée comme brouillon non public. | Vers SUPPORT_EVALUATED. |
| SUPPORT_EVALUATED | Answer | Support approfondi décidé. | Vers COMPLETED, COVERAGE_INSUFFICIENT ou REJECTED. |
| COMPLETED | Answer | Synthèse publiée avec statut, citations, contradictions et lacunes. | Terminal pour cette version. |
| REJECTED | ResearchCase | Demande ou brouillon non publiable. | Terminal pour cette version. |

## Ports et adaptateurs RA approfondie

| Port | Responsabilité | Interdiction |
|---|---|---|
| KnowledgeSearch | Obtenir des preuves candidates KA par contrat publié. | Aucun accès à Qdrant, collection, point id ou profil de stockage. |
| ProjectionVersionCatalog | Fournir les versions de projection consultées. | Ne donne pas accès aux tables internes KA. |
| VerifiedClaimCatalog | Lire VerifiedClaimRef, VerifiedClaimVersionRef et dépendances publiées par EG. | Aucune lecture du registre EG interne ni mutation de claim. |
| DeepResearchPlanner | Proposer un DeepResearchPlan structuré. | Ne collecte pas de preuves et ne publie pas de synthèse. |
| CoverageObligationEvaluator | Évaluer les CoverageObligation. | Ne transforme pas une obligation manquante en succès implicite. |
| EvidenceDiversifier | Diversifier requêtes et preuves retenues. | Ne traite pas la répétition documentaire comme indépendance. |
| ClaimDependencyResolver | Résoudre IndependentEvidenceGroup et dépendances EG. | Ne crée pas de claim ni de groupe sans version publiée. |
| ContradictionClassifier | Classer ConditionalContradiction et non-comparabilité. | Ne généralise pas hors conditions comparables. |
| MultiSourceSynthesizer | Produire une MultiSourceSynthesis proposée. | Ne décide pas DeepResearchSupportStatus et ne masque pas les lacunes. |
| CitationResolver | Vérifier l'ouverture des citations vers SourceLocator. | Ne remplace pas un SourceLocator invalide par un chemin local. |
| ResearchCaseRepository | Persister l'état RA local du ResearchCase. | Ne persiste pas d'état EG, KA ou SP propriétaire. |
| DeepResearchMetricsPublisher | Publier métriques et traces de couverture. | Ne publie pas prompt, réponse complète ou payload documentaire complet. |

## Événements RA approfondie

| Événement | Déclencheur | Payload publié |
|---|---|---|
| DeepResearchRequested | Mandat explicite accepté. | research_case_id; research_mode; mandate_hash; policy_version |
| DeepResearchPlanCreated | Plan validé. | research_case_id; plan_version; sub_question_count; coverage_obligation_count |
| CoverageObligationDeclared | Obligation figée. | research_case_id; obligation_id; coverage_axis; required_polarity |
| DeepResearchEvidenceCollected | Preuves candidates collectées. | research_case_id; projection_version_ref; evidence_count; query_count |
| EvidenceDiversificationCompleted | Diversification évaluée. | research_case_id; favorable_count; unfavorable_count; neutral_count; independent_group_count |
| ClaimDependencyGroupResolved | Dépendance EG résolue. | research_case_id; verified_claim_version_ref; dependency_group_id |
| ConditionalContradictionDetected | Contradiction ou non-comparabilité classée. | research_case_id; contradiction_type; affected_claim_refs; condition_summary |
| DocumentaryGapRecorded | Lacune documentaire enregistrée. | research_case_id; obligation_id; gap_type; public_reason |
| DeepResearchCoverageInsufficient | Couverture minimale absente. | research_case_id; missing_obligation_count; support_status |
| MultiSourceSynthesisDrafted | Synthèse proposée. | answer_id; research_case_id; synthesis_hash; model_provenance |
| DeepResearchSupportEvaluated | Support approfondi décidé. | answer_id; support_status; policy_version; contradiction_count; gap_count |
| DeepResearchCompleted | Synthèse publiée. | answer_id; answer_version; evidence_set_version; citation_count; support_status |
| DeepResearchPublicationBlocked | Publication interdite. | answer_id; support_status; public_error_code |

## API publique RA approfondie

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/research/deep | 202 ou 200 avec DeepResearchSupportStatus, plan_version, coverage_summary, citations, contradictions, gaps et synthesis_ref. | HTTP_REQUEST_INVALID; DEEP_RESEARCH_MANDATE_REQUIRED; DEEP_RESEARCH_MODE_REQUIRED; DEEP_RESEARCH_PLAN_REQUIRED; COVERAGE_OBLIGATION_MISSING; COVERAGE_INSUFFICIENT; SOURCE_DIVERSIFICATION_INSUFFICIENT; CLAIM_DEPENDENCY_UNRESOLVED; CONTRADICTION_UNCLASSIFIED; DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED; CURRENT_DATA_REQUIRED; DEEP_RESEARCH_POLICY_MISSING; PUBLIC_STORAGE_FIELD_FORBIDDEN | resolved_question; research_mandate; research_mode; selected_documents; idempotency_key; occurred_at |

### Champs publics interdits

| Endpoint | Champs interdits |
|---|---|
| POST /v1/research/deep | qdrant_collection; qdrant_point_id; eg_registry_table; sp_table; prompt_override; support_status_override; strategy_parameter; market_price_override; raw_projection_payload |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête invalide ou champ public interdit. |
| ENDPOINT_NOT_FOUND | 404 | Endpoint RA approfondi inconnu. |
| DEEP_RESEARCH_MANDATE_REQUIRED | 422 | Mandat explicite absent. |
| DEEP_RESEARCH_MODE_REQUIRED | 422 | Mode `RECHERCHE_APPROFONDIE` absent ou incohérent. |
| DEEP_RESEARCH_PLAN_REQUIRED | 409 | Plan approfondi absent avant collecte ou synthèse. |
| COVERAGE_OBLIGATION_MISSING | 422 | Obligation de couverture absente ou vide. |
| COVERAGE_INSUFFICIENT | 422 | Couverture minimale non atteinte. |
| SOURCE_DIVERSIFICATION_INSUFFICIENT | 422 | Diversification de sources ou polarités insuffisante. |
| CLAIM_DEPENDENCY_UNRESOLVED | 409 | Groupe de dépendance ou version de claim non résolu. |
| CONTRADICTION_UNCLASSIFIED | 409 | Contradiction pertinente sans classification conditionnelle. |
| DEEP_RESEARCH_SYNTHESIS_UNSUPPORTED | 422 | Synthèse non supportée par couverture, preuves, claims ou citations. |
| CURRENT_DATA_REQUIRED | 422 | Données actuelles nécessaires mais non autorisées. |
| DEEP_RESEARCH_POLICY_MISSING | 422 | Version de politique RA approfondie absente. |
| PUBLIC_STORAGE_FIELD_FORBIDDEN | 400 | Champ de stockage interne exposé dans le contrat public. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| deep_research_requested_total | Métrique | Compte les demandes avec mandat explicite. |
| deep_research_plan_created_total | Métrique | Compte les plans créés par version de politique. |
| deep_research_coverage_obligation_met_total | Métrique | Compte les CoverageObligation couvertes. |
| deep_research_coverage_obligation_missing_total | Métrique | Compte les obligations manquantes ou insuffisantes. |
| deep_research_query_executed_total | Métrique | Compte les requêtes KA par plan sans payload documentaire complet. |
| deep_research_independent_source_group_total | Métrique | Compte les IndependentEvidenceGroup retenus. |
| deep_research_contradiction_classified_total | Métrique | Compte les ConditionalContradiction classées. |
| deep_research_documentary_gap_total | Métrique | Compte les DocumentaryGap par type. |
| deep_research_support_status_total | Métrique | Compte les DeepResearchSupportStatus publiés. |
| deep_research_public_error_total | Métrique | Compte les erreurs publiques par code. |
| deep_research_synthesis_published_total | Métrique | Compte les synthèses publiées par statut. |
| deep_research_claim_version_recorded_total | Trace | Compte les VerifiedClaimVersionRef enregistrées sans payload EG interne. |

## Comportements vérifiables M-009

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| DRA-001 - Spécification exécutable M-009 | La spécification nomme mission RA approfondie, mode, plan, obligations, dépendances EG, contradictions, API, erreurs, métriques, exclusions et garde-fous. | Given la mission M-009 est d'analyser plusieurs sources sans effacer nuances, limites et contradictions; When la spécification de recherche approfondie est publiée; Then elle est validée par commande PowerShell. | T-002 | ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005; DDD-ADR-007; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1 |
| DRA-002 - Plan de recherche avec obligations | Un ResearchCase approfondi possède DeepResearchPlan et CoverageObligation avant collecte. | Given une question autonome et un mandat approfondi; When RA planifie la recherche; Then chaque sous-question porte une obligation vérifiable. | T-003 | ADR-006; ADR-010; DDD-ADR-005 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_planning_acceptance.ps1 |
| DRA-003 - Collecte multi-requêtes diversifiée | Les preuves favorables et défavorables sont collectées sans confondre répétition et indépendance. | Given un plan avec plusieurs obligations; When RA collecte les preuves; Then les requêtes, sources et polarités sont tracées. | T-004 | ADR-006; DDD-ADR-003; DDD-ADR-005 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_query_evidence_collection_acceptance.ps1 |
| DRA-004 - Claims et dépendances EG indépendantes | Les versions de claims et groupes de dépendance sont enregistrés avant synthèse. | Given plusieurs claims issus de sources liées; When RA résout les dépendances; Then un même groupe ne compte pas comme confirmations indépendantes multiples. | T-005 | ADR-006; DDD-ADR-005; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_verified_claim_dependency_resolution_acceptance.ps1 |
| DRA-005 - Contradictions conditionnelles | Une contradiction pertinente conserve conditions, horizon, univers et métrique. | Given deux affirmations opposées portant sur des horizons différents; When l'analyse des contradictions est exécutée; Then la relation est classée DIFFERENT_HORIZON et la réponse explique la condition. | T-006 | DDD-ADR-005; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_contradiction_classification_acceptance.ps1 |
| DRA-006 - Couverture insuffisante explicite | Une couverture minimale absente bloque SUPPORTED. | Given une obligation critique sans preuve admissible; When RA évalue la couverture; Then COVERAGE_INSUFFICIENT est publié avec la lacune documentaire. | T-007 | ADR-006; DDD-ADR-005; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_insufficient_deep_coverage_acceptance.ps1 |
| DRA-007 - Synthèse multi-sources traçable | La synthèse distingue source, déduction et choix de conception. | Given une collecte avec preuves, contradictions et lacunes; When RA synthétise; Then chaque conclusion est rattachée à provenance et qualification. | T-008 | DDD-ADR-003; DDD-ADR-005; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_multi_source_synthesis_acceptance.ps1 |
| DRA-008 - Endpoint recherche approfondie | POST /v1/research/deep expose le contrat RA sans stockage interne. | Given un mandat approfondi valide; When l'endpoint est appelé; Then le corps public ne contient ni Qdrant, ni table EG, ni champ de stockage SP. | T-009 | ADR-010; DDD-ADR-003; DDD-ADR-005 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_deep_research_http_contract_acceptance.ps1 |
| DRA-009 - Métriques de couverture et audit | Les métriques relient couverture, contradictions, lacunes, versions et statuts sans payload complet. | Given une recherche approfondie terminée ou bloquée; When les signaux sont publiés; Then ils exposent versions et compteurs sans contenu documentaire complet. | T-010 | ADR-010; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_coverage_metrics_acceptance.ps1 |
| DRA-010 - Traçabilité et gates M-009 | Chaque exigence M-009 possède test, commande, ADR et artefact cible. | Given les comportements M-009 sont implémentés; When les gates s'exécutent; Then traceability, test, lint et validate_m009_specification sont enrôlés. | T-011 | ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_traceability_acceptance.ps1 |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m009\validate_m009_specification_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m009_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-009

- M-009 T-002 ne livre pas les agrégats, repositories, adaptateurs HTTP ou endpoint RA approfondi.
- M-009 T-002 ne livre pas les tâches T-003 à T-011; elle publie leur contrat vérifiable.
- M-009 ne livre pas la stratégie candidate attribuée M-010 ni l'expérience reproductible M-011.
- M-009 ne change pas le contrat `VerifiedResearchOutcome` publié par M-001 et utilisé par RA et CV.
- M-009 ne modifie pas le sens du registre de claims, de la cohérence éventuelle ou de la surface API existante.
- M-009 ne publie aucun prompt, brouillon, collection Qdrant, table EG, table SP, table KA ou détail de stockage comme contrat public.
- M-009 ne modifie pas la signification des ADR acceptées; ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-008 sont appliquées telles quelles.
