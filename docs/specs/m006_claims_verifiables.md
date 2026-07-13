# M-006 - Claims vérifiables

## Statut

- Milestone: M-006 - Claims vérifiables.
- ADR consultées: ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007, DDD-ADR-010.
- ADR: non requise, car M-006 applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given des preuves candidates KA avec SourceLocator résolvable.
- When la spécification M-006 est publiée.
- Then chaque comportement de claim nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission EG

EG transforme des preuves candidates en claims atomiques, vérifiés, rejetés, reliés ou supersédés. EG ne remplace ni SP pour l'autorité documentaire, ni KA pour la recherche, ni RA pour la réponse.

La mission de M-006 est de protéger le passage d'une proposition plausible à une affirmation vérifiée. Une affirmation VERIFIED DOIT posséder au moins une preuve directe admissible. La portée de l'affirmation ne peut dépasser la portée commune de ses preuves sans qualification explicite. Le LLM propose et la politique décide.

Les garde-fous de mission sont explicites: aucun claim EG stocké dans l'index documentaire; EG consomme KnowledgeSearchPort sans accès direct à Qdrant; un score n'est pas un verdict métier.

## Contexte DDD

- Domaine: gouvernance des preuves.
- Bounded context: EG.
- Objectif métier: créer, vérifier, relier et versionner les affirmations et leurs preuves.
- Intégrations: EG consomme des preuves candidates KA avec `SourceLocator`, publie des `VerifiedClaimRef` vers RA et SD, et conserve ses décisions via registre EG séparé.
- Garde-fous: aucune preuve élargie silencieusement; aucune valeur par défaut pour la politique de vérification; aucun verdict dérivé d'un score seul; aucune preuve publique sans `SourceLocator` publié.

## Langage ubiquitaire EG

| Terme | Sens M-006 |
|---|---|
| Claim | Agrégat EG qui porte une proposition atomique, sa portée, ses preuves, son état et sa version. |
| VerificationCase | Décision de vérification indépendante et immuable, rattachée à une version de claim. |
| DependencyGroup | Groupe d'origine commune utilisé pour compter les confirmations réellement indépendantes. |
| CanonicalProposition | Formulation canonique qui conserve négation, modalité, conditions et limitations. |
| SourceLocator | Localisateur publié et résolvable vers la version canonique, la page, l'item source et le hash de contenu. |
| EvidenceRef | Référence publique de preuve EG contenant `SourceLocator`, relation, hash de span et version canonique. |
| VerificationDecision | Verdict, raisons, version de modèle, version de prompt et version de politique. |
| VerifiedClaimRef | Référence publiée vers une version de claim vérifiée. |
| KnowledgeSearchPort | Port KA consommé par EG pour obtenir des preuves candidates sans dépendre de Qdrant. |
| Preuve directe admissible | EvidenceRef résolvable dont la relation est `SUPPORTS_DIRECTLY` et dont la portée couvre le claim. |

## Agrégats EG

| Agrégat | Responsabilité M-006 | Invariants | Événements |
|---|---|---|---|
| Claim | Porter le cycle de vie d'une proposition atomique, de DRAFT à VERIFIED, REJECTED, SUPERSEDED ou ABANDONED. | Une transition vers VERIFIED exige preuve directe admissible, portée compatible, verdict autorisé et décision indépendante. | ClaimDrafted; EvidenceAttachedToClaim; ClaimSubmittedForVerification; ClaimVerified; ClaimRejected; ClaimDependencyAssigned; ClaimRelationRecorded; ClaimSuperseded |
| VerificationCase | Enregistrer une décision de vérification immuable pour une version de claim. | La décision contient verdict, raisons, preuves prémisses, version de modèle, version de prompt et version de politique. | VerificationDecisionRecorded |
| DependencyGroup | Représenter une origine intellectuelle ou empirique commune. | Plusieurs mentions du même groupe ne valent qu'une confirmation indépendante. | ClaimDependencyAssigned |

## Objets-valeur EG

| Objet-valeur | Sens M-006 | Invariants |
|---|---|---|
| ClaimId | Identité stable du claim. | Jamais dérivée d'un identifiant Qdrant ou d'un chemin documentaire. |
| ClaimVersion | Version métier du claim. | Toute modification de proposition crée une nouvelle version. |
| CanonicalProposition | Proposition atomique normalisée. | Ne supprime ni négation, ni modalité, ni condition. |
| ClaimScope | Univers, horizon, fréquence, métrique et limites du claim. | Ne peut pas être plus large que les preuves sans qualification explicite. |
| ClaimCondition | Condition nécessaire à la validité du claim. | Obligatoire si elle apparaît dans le span ou son contexte immédiat. |
| Limitation | Restriction ou avertissement issu de la preuve. | Conservée dans la proposition ou la portée. |
| EvidenceRef | Référence de preuve attachée au claim. | Contient un SourceLocator résolvable, relation, hash de span et version canonique. |
| SourceLocator | Langage publié de citation documentaire. | Ne pointe pas vers une version retirée ou en quarantaine sans refus explicite. |
| VerificationVerdict | Verdict de vérification. | Valeurs autorisées par politique, jamais déduites d'un score seul. |
| ReasonCode | Raison publique de décision. | Obligatoire pour tout rejet ou refus de portée. |
| CalibratedScore | Mesure auxiliaire de modèle. | N'est jamais un verdict métier. |

## Politiques normatives M-006

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| ClaimAtomicityPolicy | Découpe une proposition en claims vérifiables séparément. | Un claim large ou composite reste DRAFT refusé pour vérification. | DDD-ADR-005 |
| EvidenceAdmissibilityPolicy | Accepte seulement des EvidenceRef directs, résolvables et cohérents. | `SUPPORTS_DIRECTLY` et SourceLocator publié sont requis pour vérifier. | ADR-006; DDD-ADR-003 |
| ClaimVerificationPolicy | Autorise ou refuse la transition de UNDER_VERIFICATION vers VERIFIED ou REJECTED. | Le verdict autorisé et les raisons explicites décident, pas le score. | DDD-ADR-005; DDD-ADR-007 |
| ScopePreservationPolicy | Compare portée du claim et portée commune des preuves. | CLAIM_SCOPE_EXCEEDS_EVIDENCE bloque la vérification. | DDD-ADR-005 |
| SourceIndependencePolicy | Compte les groupes de dépendance indépendants. | Une source secondaire citant l'étude primaire ne compte pas comme confirmation indépendante. | ADR-006 |
| ClaimCanonicalizationPolicy | Normalise la proposition sans perdre conditions, limitations, négation ou modalité. | La sortie modèle reste proposition tant que la politique n'a pas décidé. | DDD-ADR-005; DDD-ADR-007 |
| ClaimRelationPolicy | Relie support, contradiction, généralisation et dépendance entre versions de claims. | Une contradiction exige comparaison de portée. | DDD-ADR-005; DDD-ADR-010 |
| HumanReviewEscalationPolicy | Escalade explicitement un cas non décidable par politique automatique. | Aucune revue humaine implicite ne remplace une décision de domaine. | DDD-ADR-007 |

## Machine d'états M-006

| État | Portée | Sens M-006 | Transition autorisée |
|---|---|---|---|
| DRAFT | Claim | Proposition candidate extraite sans preuve encore admise. | Vers EVIDENCE_ATTACHED ou ABANDONED. |
| EVIDENCE_ATTACHED | Claim | Au moins une preuve admissible est rattachée sans verdict. | Vers UNDER_VERIFICATION, SUPERSEDED ou ABANDONED. |
| UNDER_VERIFICATION | Claim | Une décision indépendante est en cours ou enregistrée. | Vers VERIFIED ou REJECTED. |
| VERIFIED | Claim | Le claim est vérifié pour sa portée et sa version. | Vers SUPERSEDED. |
| REJECTED | Claim | La vérification est refusée avec raisons. | Terminal pour cette version. |
| SUPERSEDED | Claim | Une version ou formulation meilleure remplace explicitement celle-ci. | Terminal pour cette version. |
| ABANDONED | Claim | Le brouillon est abandonné avant publication. | Terminal pour cette version. |

## Ports et adaptateurs EG

| Port | Responsabilité | Interdiction |
|---|---|---|
| CanonicalEvidenceReader | Résoudre les EvidenceRef et SourceLocator publiés par SP. | Ne lit pas les tables internes SP. |
| KnowledgeSearchPort | Obtenir des preuves candidates KA. | Aucun accès direct à Qdrant. |
| ClaimExtractor | Produire des propositions structurées depuis des preuves candidates. | N'auto-approuve jamais un claim. |
| IndependentClaimVerifier | Proposer verdict, raisons et score auxiliaire. | Ne modifie pas l'état métier directement. |
| DependencyResolver | Identifier ou affecter des DependencyGroup explicites. | Aucun regroupement par défaut. |
| ClaimRepository | Persister les versions de claims et états publics EG. | Ne supprime pas les claims vérifiés, rejetés ou supersédés. |
| VerificationCaseRepository | Persister les décisions de vérification immuables. | Ne remplace pas une décision existante. |
| DependencyGroupRepository | Persister les groupes de dépendance. | Ne fusionne pas silencieusement deux groupes. |
| ClaimRelationRepository | Persister les relations entre versions de claims. | Ne crée pas de contradiction sans comparaison de portée. |
| HumanReviewQueue | Exposer les cas explicitement escaladés. | Aucun fallback silencieux vers revue humaine. |

## Événements EG

| Événement | Déclencheur | Payload publié |
|---|---|---|
| ClaimDrafted | Une extraction structurée produit un claim DRAFT. | claim_id; claim_version; proposition_hash; source_locator; extractor_version |
| EvidenceAttachedToClaim | Une preuve admissible est attachée au claim. | claim_id; claim_version; evidence_ref; evidence_relation |
| ClaimSubmittedForVerification | Un claim avec preuve est soumis à vérification. | claim_id; claim_version; verification_case_id; policy_version |
| VerificationDecisionRecorded | Le verdict et ses raisons sont enregistrés. | verification_case_id; claim_id; verdict; reason_codes; model_version; prompt_version; policy_version |
| ClaimVerified | La décision autorise VERIFIED. | claim_id; claim_version; verified_claim_ref; accepted_verification_id |
| ClaimRejected | La décision refuse la vérification. | claim_id; claim_version; reason_codes; rejected_at |
| ClaimDependencyAssigned | Un claim est rattaché à un DependencyGroup. | claim_id; claim_version; dependency_group_id; dependency_kind |
| ClaimRelationRecorded | Une relation entre versions de claims est créée. | source_claim_ref; target_claim_ref; relation_type; scope_compatibility |
| ClaimSuperseded | Une version est remplacée sans effacement. | old_claim_ref; new_claim_ref; supersession_reason |
| ClaimApprovedByHuman | Une revue humaine explicite approuve une décision. | claim_id; claim_version; reviewer_id; reason_codes |
| ClaimRejectedByHuman | Une revue humaine explicite rejette une décision. | claim_id; claim_version; reviewer_id; reason_codes |

## API publique EG

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/claims/extract | 202 CLAIM_EXTRACTION_ACCEPTED quand les preuves candidates sont acceptées pour extraction. | 400 HTTP_REQUEST_INVALID; 403 CLAIM_CONTEXT_FORBIDDEN; 422 CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE; 422 CLAIM_PUBLICATION_FORBIDDEN. | request_id; draft_claims; rejected_candidates; trace_id. |
| POST /v1/claims/{claim_id}/verify | 200 CLAIM_VERIFICATION_RECORDED quand une décision est enregistrée. | 400 HTTP_REQUEST_INVALID; 403 CLAIM_CONTEXT_FORBIDDEN; 404 CLAIM_NOT_FOUND; 409 CLAIM_STATE_INVALID; 422 CLAIM_EVIDENCE_REQUIRED; 422 CLAIM_SCOPE_EXCEEDS_EVIDENCE; 422 INSUFFICIENT_DIRECT_EVIDENCE; 422 CLAIM_VERIFICATION_POLICY_MISSING. | status; claim_id; claim_version; verification_case_id; state; verdict; reason_codes; verified_claim_ref. |
| GET /v1/claims/{claim_id} | 200 CLAIM_READ quand la version demandée est consultable. | 404 CLAIM_NOT_FOUND; 409 CLAIM_PUBLICATION_FORBIDDEN. | claim_id; claim_version; state; canonical_proposition; scope; superseded_by; verified_claim_ref. |
| GET /v1/claims/{claim_id}/evidence | 200 CLAIM_EVIDENCE_READ quand les preuves publiques sont résolubles. | 404 CLAIM_NOT_FOUND; 409 CLAIM_PUBLICATION_FORBIDDEN; 422 CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE. | claim_id; claim_version; evidence_refs; dependency_groups; verification_cases. |

### Corps de requête publics

| Endpoint | Champs acceptés | Champs interdits |
|---|---|---|
| POST /v1/claims/extract | evidence_candidates; extraction_schema_version; requested_by_context; idempotency_key; occurred_at | qdrant_collection; prompt_override; verified_state |
| POST /v1/claims/{claim_id}/verify | verification_policy_version; verifier_profile_id; idempotency_key; occurred_at | verdict_override; calibrated_score_as_verdict; qdrant_point_id |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête EG invalide. |
| CLAIM_CONTEXT_FORBIDDEN | 403 | Contexte authentifié non autorisé à muter les claims EG. |
| CLAIM_NOT_FOUND | 404 | Claim inconnu ou version absente. |
| CLAIM_STATE_INVALID | 409 | Transition interdite pour l'état courant du claim. |
| CLAIM_EVIDENCE_REQUIRED | 422 | Aucune preuve admissible n'est attachée. |
| CLAIM_EVIDENCE_SOURCE_UNRESOLVABLE | 422 | SourceLocator absent, non résolvable ou incohérent. |
| CLAIM_SCOPE_EXCEEDS_EVIDENCE | 422 | La portée du claim dépasse la portée commune des preuves. |
| INSUFFICIENT_DIRECT_EVIDENCE | 422 | Aucune preuve SUPPORTS_DIRECTLY admissible ne soutient directement le claim. |
| CLAIM_VERIFICATION_POLICY_MISSING | 422 | La version de politique de vérification est absente. |
| CLAIM_PUBLICATION_FORBIDDEN | 409 | L'état ou la source interdit la publication publique. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| claims_drafted_total | Métrique | Compte les claims DRAFT créés sans payload documentaire complet. |
| claims_verified_total | Métrique | Compte les transitions VERIFIED par verdict et politique. |
| claims_rejected_total | Métrique | Compte les refus par ReasonCode. |
| claim_verification_latency_seconds | Métrique | Mesure le délai de vérification sans texte de claim complet. |
| claim_scope_refusal_total | Métrique | Compte les refus CLAIM_SCOPE_EXCEEDS_EVIDENCE. |
| claim_independent_support_groups | Métrique | Compte les DependencyGroup indépendants par claim. |
| claim_superseded_total | Métrique | Compte les supersessions conservées. |
| claim_model_proposal_total | Trace | Compte les propositions de modèle sans les traiter comme décisions. |
| claim_public_evidence_resolution_failed_total | Métrique | Compte les EvidenceRef publics non résolubles. |

## Comportements vérifiables M-006

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| EG-001 - Spécification exécutable M-006 | La spécification nomme mission EG, agrégats, objets-valeur, politiques, états, ports, événements, API, erreurs, métriques, exclusions et garde-fous. | Given des preuves candidates KA avec SourceLocator résolvable; When la spécification M-006 est publiée; Then elle est validée par commande uv run --locked gate
| EG-002 - Extraction atomique structurée | Une sortie de modèle crée seulement des claims DRAFT atomiques. | Given un passage avec deux conclusions et une limitation; When EG extrait les claims candidats; Then deux claims DRAFT conservent portée, limitation et span. | T-003 | ADR-006; DDD-ADR-005; DDD-ADR-007 | uv run --locked gate
| EG-003 - Preuves admissibles avec SourceLocator | Toute preuve publique contient EvidenceRef, SourceLocator, relation et hash de span. | Given un claim DRAFT et une preuve candidate résoluble; When la preuve SUPPORTS_DIRECTLY est attachée; Then le claim devient EVIDENCE_ATTACHED. | T-004 | DDD-ADR-003; DDD-ADR-005 | uv run --locked gate
| EG-004 - Vérification par preuve directe et portée | VERIFIED exige preuve directe admissible, portée compatible et décision indépendante. | Given une affirmation EVIDENCE_ATTACHED; When aucune preuve SUPPORTS_DIRECTLY admissible n'existe; Then VERIFIED est refusé avec INSUFFICIENT_DIRECT_EVIDENCE. | T-005 | ADR-006; DDD-ADR-005; DDD-ADR-007 | uv run --locked gate
| EG-005 - Confirmations indépendantes par DependencyGroup | Plusieurs documents du même DependencyGroup comptent comme une seule confirmation indépendante. | Given trois documents rattachés au même DependencyGroup; When le support indépendant est calculé; Then une seule confirmation est comptabilisée. | T-006 | ADR-006; DDD-ADR-005; DDD-ADR-010 | uv run --locked gate
| EG-006 - Relations après comparaison de portée | Une contradiction exige portée comparable et versions explicites. | Given deux claims opposés avec horizons différents; When EG évalue leur relation; Then CONTRADICTS n'est pas créé et la non-comparabilité est enregistrée. | T-007 | DDD-ADR-005; DDD-ADR-010 | uv run --locked gate
| EG-007 - Conservation des claims rejetés et supersédés | Les rejets et supersessions restent consultables. | Given un claim vérifié publié; When une meilleure formulation le supersède; Then l'ancienne version reste résoluble et pointe vers la nouvelle. | T-008 | ADR-006; DDD-ADR-005; DDD-ADR-010 | uv run --locked gate
| EG-008 - API claims et preuves publiques | L'API expose handlers EG, erreurs stables et EvidenceRef résolubles sans stockage interne. | Given un claim vérifié avec preuves directes; When GET /v1/claims/{claim_id}/evidence est appelé; Then les preuves publiques sont retournées sans prompt ni détail de stockage. | T-009 | ADR-006; ADR-010; DDD-ADR-003; DDD-ADR-005 | uv run --locked gate
| EG-009 - Traçabilité et métriques M-006 | Chaque exigence M-006 possède test, commande, ADR et métrique sans payload documentaire complet. | Given les preuves M-006; When les gates s'exécutent; Then traceability, test, lint et validate_m006_specification sont enrôlés. | T-010 | ADR-006; ADR-010; DDD-ADR-005; DDD-ADR-010 | uv run --locked gate

## Commandes de validation

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-006

- M-006 ne choisit pas de stockage de graphe spécialisé ni de nouvelle technologie de persistance durable.
- M-006 ne publie pas de réponse RA, de stratégie SD ou de résultat d'expérience.
- M-006 ne rend pas les scores NLI, embeddings ou rerankers autoritaires.
- M-006 ne modifie pas la signification des ADR acceptées; ADR-006, ADR-010, DDD-ADR-003, DDD-ADR-005, DDD-ADR-007 et DDD-ADR-010 sont appliquées telles quelles.
