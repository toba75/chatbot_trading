# M-008 - Conversation produit

## Statut

- Milestone: M-008 - Conversation produit.
- ADR consultées: ADR-010, DDD-ADR-001, DDD-ADR-002, DDD-ADR-003, DDD-ADR-007, DDD-ADR-008.
- ADR: non requise, car M-008 applique les décisions existantes sans changer leur sens.

## Scénario BDD

- Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite.
- When la spécification de conversation produit est publiée.
- Then chaque comportement CV nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission CV

CV gère l'expérience conversationnelle: conversations, tours, contexte compact, résolution des références de suivi, sélection de mode, rattachement de résultats vérifiés et présentation produit. CV ne possède aucune vérité documentaire, ne décide pas une preuve et ne modifie pas les agrégats RA, EG, KA, SP, SD ou EX.

L'historique conversationnel n'est jamais une preuve autonome. Une question de suivi est résolue en question autonome avant tout appel à RA, SD ou EX. Le mode sélectionné et sa justification synthétique sont enregistrés dans le tour. Toute assertion historique réutilisée sans VerifiedAnswerVersion est renvoyée à RA pour revalidation avant présentation. Le DTO public RA de présentation expose answer_text et citations sans modifier `VerifiedResearchOutcome`. `VerifiedResearchOutcome` ne porte ni answer_text ni citations.

Les garde-fous de mission sont explicites: aucun prompt ni résumé interne n'est publié comme source de vérité; aucun fallback de mode n'est appliqué; aucune valeur par défaut de mode n'est implicite; aucune exposition de stockage RA, KA, EG ou SP n'entre dans le contrat public; l'archivage conversationnel ne supprime pas les connaissances, réponses, stratégies ou expériences déclenchées.

## Contexte DDD

- Domaine: conversation produit fondée sur preuves.
- Bounded context: CV.
- Objectif métier: offrir un chatbot local utile tout en séparant continuité du dialogue et établissement des faits.
- Intégrations: CV appelle RA avec une `ResolvedQuestion` et un mandat explicite, reçoit `AnswerQuestionResult`, présente le texte et les citations du DTO public RA, et conserve seulement des références vers `VerifiedResearchOutcome`, stratégies et expériences.
- Garde-fous: aucune mutation d'agrégat RA depuis CV; aucun accès direct aux stockages RA, KA, EG ou SP; aucune réutilisation factuelle sans `VerifiedAnswerVersion` ou revalidation RA.

## Langage ubiquitaire CV

| Terme | Sens M-008 |
|---|---|
| Conversation | Agrégat CV qui porte identité, titre, préférences, statut et dernier snapshot compact. |
| ConversationTurn | Agrégat append-only qui porte message, question résolue, mode sélectionné, résultat attaché et présentation publiée. |
| ConversationContextSnapshot | Objet-valeur compact qui distingue préférences utilisateur, références vérifiées, ambiguïtés et contraintes de présentation. |
| ResolvedQuestion | Question autonome produite avant appel à RA, SD ou EX. |
| ConversationMode | Mode explicite parmi CHAT_DOCUMENTAIRE, RECHERCHE_APPROFONDIE, COMPARAISON, CONCEPTION_STRATEGIE, CALCUL, BACKTEST et CLARIFICATION_INTERNE. |
| ConversationModeSelection | Décision de routage avec mode, justification synthétique et politique utilisée. |
| VerifiedAnswerVersion | Version RA immuable qui autorise la réutilisation factuelle d'une réponse historique. |
| AnswerQuestionResult | DTO public RA consommé par CV pour présenter answer_text, citations et statut sans élargir `VerifiedResearchOutcome`. |
| PublicAnswerPresentationDto | DTO CV de présentation produit qui reprend texte, citations ouvrables, statut documentaire et lacunes. |
| HistoricalAssertionRef | Référence CV vers une assertion déjà formulée et sa preuve de revalidation ou sa VerifiedAnswerVersion. |

## Agrégats CV

| Agrégat | Responsabilité M-008 | Invariants | Événements |
|---|---|---|---|
| Conversation | Créer et nommer une conversation, conserver préférences et statut, référencer le dernier ConversationContextSnapshot, archiver sans cascade. | Conversation active requise pour ajouter un tour; historique interdit comme preuve autonome; archivage sans suppression des résultats déclenchés. | ConversationCreated; ConversationPreferencesUpdated; ConversationArchived |
| ConversationTurn | Enregistrer chaque message ou réponse en append-only avec question résolue, mode sélectionné, résultat attaché et présentation publiée. | Tour rattaché à une Conversation existante; question résolue avant appel aval; mode et justification obligatoires; résultat vérifié attaché par référence. | UserTurnAppended; FollowUpQuestionResolved; ConversationModeSelected; VerifiedAnswerAttachedToTurn; StrategyAttachedToTurn; ExperimentAttachedToTurn; ConversationPublicResponsePresented |

## Objets-valeur CV

| Objet-valeur | Sens M-008 | Invariants |
|---|---|---|
| ConversationId | Identifiant opaque de conversation. | Obligatoire pour chaque tour et endpoint interne. |
| ConversationTurnId | Identifiant opaque de tour append-only. | Jamais réutilisé pour corriger un tour existant. |
| ConversationContextSnapshot | Contexte compact utile à la continuité. | Ne recopie pas tous les tours et ne devient pas une preuve documentaire. |
| ResolvedQuestion | Question autonome prête pour RA, SD ou EX. | Mentionne explicitement les références résolues avant routage. |
| ConversationMode | Mode explicite demandé ou sélectionné. | Aucun mode inconnu ou implicite n'est accepté. |
| ConversationModeSelection | Mode, justification et politique de sélection. | Justification synthétique obligatoire. |
| HistoricalAssertionRef | Assertion historique candidate à réutilisation. | Doit référencer VerifiedAnswerVersion ou déclencher revalidation RA. |
| VerifiedAnswerVersionRef | Référence vers une version RA immuable attachée au tour. | Obligatoire pour réutilisation factuelle sans nouvelle recherche. |
| PublicAnswerPresentationDto | Présentation CV issue du DTO public RA. | Contient texte, citations et statut sans modifier `VerifiedResearchOutcome`. |
| ConversationRetentionDecision | Décision d'archivage ou conservation locale CV. | Ne supprime pas les connaissances, claims, réponses, stratégies ou expériences déclenchées. |

## Politiques normatives M-008

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| ReferenceResolutionPolicy | Transforme un suivi en question autonome avant appel aval. | Une référence ambiguë produit clarification et non appel implicite. | DDD-ADR-007 |
| ConversationModeRoutingPolicy | Sélectionne un mode explicite et justifié. | Aucun fallback de mode; mode inconnu refusé. | ADR-010; DDD-ADR-007 |
| ConversationContextCompactionPolicy | Construit un snapshot compact traçable. | Le snapshot distingue préférences, faits vérifiés et ambiguïtés. | DDD-ADR-003; DDD-ADR-007 |
| VerifiedResultReusePolicy | Autorise une réutilisation factuelle seulement avec VerifiedAnswerVersion ou revalidation RA. | Toute assertion historique sans VerifiedAnswerVersion est revalidée par RA. | DDD-ADR-003; DDD-ADR-007; DDD-ADR-008 |
| PublicAnswerPresentationPolicy | Présente texte, citations et statut depuis `AnswerQuestionResult`. | `VerifiedResearchOutcome` reste distinct du DTO public RA. | DDD-ADR-002; DDD-ADR-003 |
| ConversationRetentionPolicy | Archive CV sans supprimer les résultats métier aval. | Les connaissances, claims, réponses, stratégies et expériences déclenchées survivent à l'archive. | DDD-ADR-002; DDD-ADR-008 |
| ChatCompatibilityPolicy | Adapte `/v1/chat/completions` vers les commandes CV sans importer le protocole externe dans le domaine. | Aucun chat générique ni option non supportée n'est accepté silencieusement. | ADR-010; DDD-ADR-001 |

## Machine d'états M-008

| État | Portée | Sens M-008 | Transition autorisée |
|---|---|---|---|
| ACTIVE | Conversation | Conversation ouverte et modifiable par ajout de tours. | Vers ARCHIVED. |
| ARCHIVED | Conversation | Conversation fermée aux nouveaux tours. | Terminal pour CV. |
| USER_TURN_APPENDED | ConversationTurn | Message utilisateur enregistré. | Vers QUESTION_RESOLVED ou CLARIFICATION_REQUIRED. |
| QUESTION_RESOLVED | ConversationTurn | Question autonome produite. | Vers MODE_SELECTED. |
| MODE_SELECTED | ConversationTurn | Mode explicite et justification enregistrés. | Vers DISPATCHED_TO_RA, DISPATCHED_TO_SD, DISPATCHED_TO_EX ou PRESENTED. |
| DISPATCHED_TO_RA | ConversationTurn | RA appelée avec ResolvedQuestion et mandat explicite. | Vers VERIFIED_RESULT_ATTACHED ou REJECTED. |
| DISPATCHED_TO_SD | ConversationTurn | SD appelée avec demande de stratégie explicite. | Vers VERIFIED_RESULT_ATTACHED ou REJECTED. |
| DISPATCHED_TO_EX | ConversationTurn | EX consulté avec référence d'expérience explicite. | Vers VERIFIED_RESULT_ATTACHED ou REJECTED. |
| VERIFIED_RESULT_ATTACHED | ConversationTurn | Réponse, stratégie ou expérience attachée par référence publiée. | Vers PRESENTED. |
| CLARIFICATION_REQUIRED | ConversationTurn | Ambiguïté demandant un nouveau message utilisateur. | Terminal pour ce tour. |
| PRESENTED | ConversationTurn | Présentation produit publiée. | Terminal pour ce tour. |
| REJECTED | ConversationTurn | Traitement refusé par politique CV ou aval. | Terminal pour ce tour. |

## Ports et adaptateurs CV

| Port | Responsabilité | Interdiction |
|---|---|---|
| QuestionResolver | Produire une ResolvedQuestion autonome depuis message et snapshot. | Ne transmet pas l'historique brut comme preuve. |
| ModeClassifier | Proposer un mode à ConversationModeRoutingPolicy. | Ne décide pas sans politique CV. |
| ConversationRepository | Persister Conversation et statut. | Ne stocke pas les états RA, EG, KA, SP, SD ou EX internes. |
| ConversationTurnRepository | Persister les tours append-only. | Ne modifie pas un tour publié. |
| ConversationContextStore | Lire et écrire ConversationContextSnapshot. | Ne recopie pas aveuglément tous les tours. |
| ResearchFacade | Appeler RA avec ResolvedQuestion et mandat. | Ne modifie pas ResearchCase, Answer ni VerifiedResearchOutcome. |
| StrategyFacade | Appeler SD avec demande explicite. | Ne compile pas de stratégie dans CV. |
| ExperimentFacade | Lire un résultat EX par référence. | Ne lance pas un backtest sans commande EX. |
| PublicAnswerPresenter | Construire PublicAnswerPresentationDto depuis AnswerQuestionResult. | Ne suppose pas que `VerifiedResearchOutcome` contient answer_text ou citations. |
| ChatCompletionsAdapter | Adapter `/v1/chat/completions` vers CV. | N'introduit pas de chat générique ni d'accès direct au LLM. |

## Événements CV

| Événement | Déclencheur | Payload publié |
|---|---|---|
| ConversationCreated | Création explicite. | conversation_id; title; created_at; policy_version |
| UserTurnAppended | Message utilisateur accepté. | conversation_id; turn_id; user_message_hash; occurred_at |
| FollowUpQuestionResolved | Référence de suivi résolue. | conversation_id; turn_id; resolved_question_hash; ambiguity_count |
| ConversationModeSelected | Mode choisi. | conversation_id; turn_id; mode; justification_hash; policy_version |
| HistoricalAssertionRevalidationRequested | Assertion historique sans VerifiedAnswerVersion réutilisée. | conversation_id; turn_id; historical_assertion_hash; reason_code |
| VerifiedAnswerAttachedToTurn | Résultat RA attaché. | conversation_id; turn_id; answer_id; support_status; verified_answer_version |
| StrategyAttachedToTurn | Stratégie attachée. | conversation_id; turn_id; strategy_id; strategy_version_id |
| ExperimentAttachedToTurn | Expérience attachée. | conversation_id; turn_id; experiment_id; result_status |
| ConversationPreferencesUpdated | Préférences explicites mises à jour. | conversation_id; preference_hash; updated_at |
| ConversationArchived | Conversation archivée. | conversation_id; archived_at; retention_policy_version |
| ConversationPublicResponsePresented | Présentation produit publiée. | conversation_id; turn_id; support_status; citation_count; presentation_hash |

## API publique CV

| Endpoint | Succès | Erreurs publiques | Corps public |
|---|---|---|---|
| POST /v1/conversations | 201 CONVERSATION_CREATED. | 400 HTTP_REQUEST_INVALID; 422 CV_POLICY_MISSING. | conversation_id; title; status; created_at. |
| GET /v1/conversations/{conversation_id} | 200 CONVERSATION_READ. | 404 CONVERSATION_NOT_FOUND. | conversation_id; title; status; created_at; updated_at. |
| GET /v1/conversations/{conversation_id}/turns | 200 CONVERSATION_TURNS_READ. | 404 CONVERSATION_NOT_FOUND. | conversation_id; turns; next_page_token. |
| POST /v1/conversations/{conversation_id}/messages | 200 CONVERSATION_TURN_PROCESSED. | 400 HTTP_REQUEST_INVALID; 404 CONVERSATION_NOT_FOUND; 409 CONVERSATION_ARCHIVED; 422 FOLLOW_UP_AMBIGUOUS; 422 CONVERSATION_MODE_UNSUPPORTED; 422 RESOLVED_QUESTION_REQUIRED; 422 HISTORICAL_ASSERTION_REVALIDATION_REQUIRED; 422 ANSWER_PUBLIC_PAYLOAD_REQUIRED. | conversation_id; turn_id; resolved_question; mode; mode_justification; answer_text; citations; support_status; knowledge_gaps; unresolved_conflicts. |
| DELETE /v1/conversations/{conversation_id} | 200 CONVERSATION_ARCHIVED. | 404 CONVERSATION_NOT_FOUND; 409 CONVERSATION_ARCHIVED. | conversation_id; status; archived_at. |
| POST /v1/chat/completions | 200 CHAT_COMPLETION_CREATED. | 400 HTTP_REQUEST_INVALID; 422 CHAT_COMPLETIONS_FIELD_UNSUPPORTED; 404 CONVERSATION_NOT_FOUND; 409 CONVERSATION_ARCHIVED. | id; object; created; model; choices; conversation_id; turn_id; support_status; citations. |

### Corps de requête publics

| Endpoint | Champs acceptés | Champs interdits |
|---|---|---|
| POST /v1/conversations | title; default_mandate; presentation_preferences; occurred_at | storage_table; prompt_override; raw_history; default_mode_fallback |
| POST /v1/conversations/{conversation_id}/messages | message; requested_mode; research_mandate; selected_documents; idempotency_key; occurred_at | qdrant_collection; qdrant_point_id; eg_registry_table; ra_storage; prompt_override; support_status_override; verified_research_outcome_text |
| POST /v1/chat/completions | model; messages; conversation_id; metadata; stream; idempotency_key | prompt_override; tool_fallback; unsupported_mode_default; qdrant_collection; eg_registry_table |

## Erreurs publiques

| Code | Statut HTTP | Sens public |
|---|---|---|
| HTTP_REQUEST_INVALID | 400 | Requête CV invalide. |
| ENDPOINT_NOT_FOUND | 404 | Endpoint CV absent pour la route demandée. |
| CONVERSATION_NOT_FOUND | 404 | Conversation inconnue. |
| CONVERSATION_TURN_NOT_FOUND | 404 | Tour inconnu ou non rattaché à la conversation. |
| CONVERSATION_ARCHIVED | 409 | Conversation archivée, ajout de tour refusé. |
| FOLLOW_UP_AMBIGUOUS | 422 | Référence de suivi ambiguë, clarification requise. |
| CONVERSATION_MODE_UNSUPPORTED | 422 | Mode demandé ou classé non supporté. |
| CONVERSATION_MODE_FORCED_UNSUPPORTED | 422 | Mode forcé par l'utilisateur incompatible avec la demande. |
| RESOLVED_QUESTION_REQUIRED | 422 | Question autonome absente avant appel aval. |
| VERIFIED_ANSWER_VERSION_REQUIRED | 422 | Réutilisation factuelle demandée sans VerifiedAnswerVersion. |
| HISTORICAL_ASSERTION_REVALIDATION_REQUIRED | 422 | Assertion historique à revalider par RA avant présentation. |
| ANSWER_PUBLIC_PAYLOAD_REQUIRED | 422 | DTO public RA incomplet pour présenter texte, citations ou statut. |
| CHAT_COMPLETIONS_FIELD_UNSUPPORTED | 422 | Champ compatible chat non supporté par la V1. |
| CV_POLICY_MISSING | 422 | Version de politique CV absente. |

## Métriques et traces

| Signal | Type | Invariant |
|---|---|---|
| conversation_created_total | Métrique | Compte les conversations créées par version de politique. |
| conversation_turn_appended_total | Métrique | Compte les tours append-only sans contenu complet. |
| follow_up_question_resolved_total | Métrique | Compte les questions autonomes produites. |
| conversation_mode_selected_total | Métrique | Compte les modes sélectionnés et forcés par politique. |
| historical_assertion_revalidated_total | Métrique | Compte les assertions historiques renvoyées à RA. |
| verified_answer_attached_total | Métrique | Compte les réponses RA attachées par statut documentaire. |
| conversation_archived_total | Métrique | Compte les archivages CV sans suppression cascade. |
| conversation_public_error_total | Métrique | Compte les erreurs publiques CV par code. |
| conversation_prompt_payload_rejected_total | Trace | Compte les payloads refusés contenant historique brut ou prompt override. |

## Comportements vérifiables M-008

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| CV-001 - Spécification exécutable M-008 | La spécification nomme mission CV, agrégats, objets-valeur, politiques, états, ports, événements, API, erreurs, métriques, exclusions et garde-fous. | Given la mission M-008 est de permettre une conversation suivie sans preuve historique implicite; When la spécification de conversation produit est publiée; Then elle est validée par commande PowerShell. | T-002 | ADR-010; DDD-ADR-001; DDD-ADR-002; DDD-ADR-003; DDD-ADR-007; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m008_specification.ps1 |
| CV-002 - Conversations et tours append-only | Un ConversationTurn appartient à une Conversation existante et n'est jamais réécrit. | Given une conversation active; When un message utilisateur est accepté; Then un tour append-only est créé. | T-003 | DDD-ADR-002; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_turn_append_only_acceptance.ps1 |
| CV-003 - Snapshot de contexte sans preuve factuelle | Le ConversationContextSnapshot compacte préférences et références vérifiées sans recopier l'historique brut. | Given plusieurs tours existent; When le snapshot est mis à jour; Then préférences, faits vérifiés et ambiguïtés restent séparés. | T-004 | DDD-ADR-003; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_context_snapshot_acceptance.ps1 |
| CV-004 - Résolution des références de suivi | Une référence conversationnelle devient une ResolvedQuestion autonome. | Given une conversation portant sur le volatility targeting; When l'utilisateur écrit compare-la maintenant à Kelly; Then la question autonome mentionne les deux méthodes. | T-005 | DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_followup_question_resolution_acceptance.ps1 |
| CV-005 - Routage de mode justifié | Le mode sélectionné est explicite et justifié. | Given une question résolue; When CV choisit un mode; Then ConversationModeSelection enregistre mode et justification sans fallback. | T-006 | ADR-010; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_mode_routing_acceptance.ps1 |
| CV-006 - Revalidation RA des assertions historiques | Toute assertion historique réutilisée sans VerifiedAnswerVersion est revalidée par RA. | Given une réponse précédente contient une assertion sans VerifiedAnswerVersion; When elle est réutilisée; Then RA reçoit une nouvelle demande de vérification. | T-007 | DDD-ADR-003; DDD-ADR-007; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_verified_result_reuse_acceptance.ps1 |
| CV-007 - Présentation produit depuis DTO public RA | Le texte et les citations viennent du DTO public RA, pas de VerifiedResearchOutcome. | Given RA retourne AnswerQuestionResult; When CV présente la réponse; Then answer_text, citations et support_status sont exposés sans modifier VerifiedResearchOutcome. | T-008 | DDD-ADR-002; DDD-ADR-003 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_chat_answer_presentation_acceptance.ps1 |
| CV-008 - Endpoints conversation et archivage | Les endpoints internes exposent conversations, tours et archivage sans stockage interne. | Given une conversation active; When les endpoints CV sont appelés; Then les réponses publiques restent bornées au contrat CV. | T-009 | ADR-010; DDD-ADR-001; DDD-ADR-002 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_conversation_http_contract_acceptance.ps1 |
| CV-009 - Compatibilité chat contrôlée | `/v1/chat/completions` adapte vers CV sans chat générique ni option silencieuse. | Given un client appelle /v1/chat/completions avec conversation_id; When CV traite la requête; Then un tour CV est créé avec statut documentaire et citations produit. | T-010 | ADR-010; DDD-ADR-001; DDD-ADR-007 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_chat_completions_contract_acceptance.ps1 |
| CV-010 - Traçabilité et métriques M-008 | Chaque exigence M-008 possède test, commande et ADR ou justification explicite. | Given les comportements M-008 sont implémentés; When les gates s'exécutent; Then traceability, test, lint et validate_m008_specification sont enrôlés. | T-011 | ADR-010; DDD-ADR-008 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_traceability_acceptance.ps1 |

## Commandes de validation

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_specification_acceptance.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m008\validate_m008_specification_unit.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m008_specification.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1
```

## Exclusions M-008

- M-008 T-002 ne livre pas les agrégats, repositories, adaptateurs HTTP ou endpoints CV.
- M-008 T-002 ne livre pas les tâches T-003 à T-011; elle publie leur contrat vérifiable.
- M-008 ne change pas le contrat `VerifiedResearchOutcome` publié par M-001 et utilisé par RA.
- M-008 ne décide pas une nouvelle durée de rétention conversationnelle ni une purge administrative.
- M-008 ne publie aucun prompt, résumé interne, collection Qdrant, table EG, table SP ou détail de stockage comme contrat public.
- M-008 ne modifie pas la signification des ADR acceptées; ADR-010, DDD-ADR-001, DDD-ADR-002, DDD-ADR-003, DDD-ADR-007 et DDD-ADR-008 sont appliquées telles quelles.
