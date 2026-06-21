# Plan d'implémentation - Milestones et Workstreams

**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`  
**Date :** 20 juin 2026  
**Produit cible :** chatbot personnel local de recherche documentaire, synthèse de stratégies de trading et backtests reproductibles sur DGX Spark.

---

## 1. Principes d'exécution

1. **Local-first strict.** Tous les services sont liés à `127.0.0.1` par défaut. Aucun service interne, modèle, Qdrant ou PostgreSQL n'est exposé publiquement.
2. **Pas de fallback silencieux.** Toute route documentaire, tout modèle, tout outil et toute citation doivent être explicites. Si une condition obligatoire n'est pas satisfaite, le système renvoie un statut contrôlé, met en quarantaine, ou bloque le traitement.
3. **PDF original immuable.** Les fichiers dans `corpus/raw/` sont traités comme source canonique visuelle et ne sont jamais modifiés.
4. **DoclingDocument JSON comme artefact canonique structuré.** Markdown, HTML, images et textes extraits sont des exports régénérables.
5. **Autorité textuelle unique par page.** Une page ne mélange jamais silencieusement texte natif, OCR et VLM.
6. **Provenance obligatoire.** Toute réponse factuelle doit pouvoir remonter au document, à la page PDF et à l'item source.
7. **LLM non calculateur.** Le LLM peut proposer, structurer et interpréter ; les calculs, signaux, positions et backtests sont exécutés par du code déterministe.
8. **Évaluation avant promotion.** Aucun modèle, seuil de routage, route documentaire ou stratégie de recherche n'est promu sans mesure sur corpus pilote.

---

## 2. Workstreams

### WS0 - Pilotage, architecture et standards

**Objectif :** garder une implémentation cohérente avec la spécification et éviter les dérives implicites.

**Responsabilités :**
- maintenir les ADR applicables ;
- maintenir le registre ADR dans `docs/adr/` ;
- définir les conventions de configuration, schémas, erreurs et statuts ;
- maintenir la matrice de conformité aux critères V1 ;
- piloter les décisions de benchmark et de promotion de modèles ;
- documenter les écarts justifiés à la spécification.

**Livrables récurrents :**
- backlog priorisé ;
- matrice `spec -> ADR -> implementation -> tests` ;
- journal des décisions ;
- définition d'achèvement par milestone.

### WS1 - Plateforme locale, sécurité et orchestration

**Objectif :** fournir le socle local DGX Spark, les services, les jobs et les profils de charge.

**Responsabilités :**
- `docker-compose.yml` ou équivalent local ;
- services `orchestrator-api`, `qdrant`, `postgres`, `gemma-vllm`, `granite-docling`, `ui`, workers ;
- ports liés à `127.0.0.1` ;
- file de jobs, priorités, idempotence ;
- profils `INGEST_BATCH`, `INTERACTIVE_RESEARCH`, `DEEP_RESEARCH`, `BACKTEST` ;
- gestion des secrets hors dépôt ;
- observabilité de base.

**Modules principaux :**
- `app/api/`
- `app/orchestration/`
- `config/security.yaml`
- `config/models.yaml`
- `config/quality_gates.yaml`

### WS2 - Données, schémas et persistance

**Objectif :** créer les contrats de données persistants et les migrations.

**Responsabilités :**
- schémas PostgreSQL pour documents, pages, conversions, chunks, claims, conversations, jobs, experiments ;
- schémas JSON/YAML pour entrées et sorties ;
- stockage des artefacts canoniques et dérivés ;
- hashes d'entrée, configuration, code et modèle ;
- contraintes d'unicité, provenance et audit.

**Modèles couverts :**
- `DocumentRecord`
- `PageDiagnostic`
- `ConversionRun`
- `DocItemRecord`
- `ChunkRecord`
- `ClaimRecord`
- `EvidenceLink`
- `ClaimRelation`
- `ConversationRecord`
- `ChatTurnRecord`
- `ExperimentRecord`

### WS3 - Ingestion, diagnostic et routage documentaire

**Objectif :** inventorier les PDF, diagnostiquer les pages et produire un plan de route sans ambiguïté.

**Responsabilités :**
- scan de `corpus/raw/` ;
- hash stable et manifeste ;
- extraction de métadonnées bibliographiques initiales ;
- diagnostic page par page ;
- classification des états de page ;
- routage vers `NATIVE_STANDARD`, `SCAN_GRANITE`, `PREPROCESS_GRANITE`, `BAD_OCR_TO_GRANITE`, `MIXED_PAGEWISE`, `TARGETED_ENRICHMENT` ;
- blocage ou revue explicite si route incertaine.

**Modules principaux :**
- `app/inventory/`
- `app/diagnostics/`
- `app/routing/`

### WS4 - Conversion Docling, QA et artefacts canoniques

**Objectif :** convertir chaque document en DoclingDocument JSON traçable, avec contrôle qualité avant indexation.

**Responsabilités :**
- conversion Docling standard ;
- rendu de pages pour VLM et contrôle visuel ;
- conversion Granite-Docling ;
- prétraitement physique conditionnel via OCRmyPDF ;
- fusion pagewise ;
- contrôle qualité pré-conversion et post-conversion ;
- mise en quarantaine explicite ;
- exports régénérables.

**Modules principaux :**
- `app/conversion/`
- `app/quality/`
- `corpus/docling/`
- `corpus/exports/`
- `corpus/quarantine/`

### WS5 - Chunking, métadonnées, embeddings et recherche hybride

**Objectif :** rendre le corpus interrogeable avec recherche dense/sparse, filtres, reranking et citations ouvrables.

**Responsabilités :**
- chunking hiérarchique ;
- enrichissement bibliographique et métier ;
- embeddings denses ;
- index sparse ou BM25 ;
- collections Qdrant ;
- fusion RRF ou DBSF ;
- reranking ;
- expansion vers fragments parents ;
- diversification par document et auteur ;
- évaluation Recall@k, MRR, nDCG.

**Modules principaux :**
- `app/chunking/`
- `app/indexing/`
- `app/retrieval/`
- `evaluation/retrieval/`

### WS6 - Chatbot, conversations et API produit

**Objectif :** exposer l'expérience utilisateur principale : conversation, suivi de contexte, classification du mode et réponses citées.

**Responsabilités :**
- API conversations ;
- endpoint compatible `/v1/chat/completions` ;
- gestion de session ;
- résolution des références conversationnelles ;
- classification de requête ;
- sélection des modes `DOCUMENTARY`, `DEEP_RESEARCH`, `STRATEGY`, `CALCULATION`, `BACKTEST` ;
- UI locale ;
- ouverture de citation vers PDF/page/zone ;
- distinction visible source, déduction et choix de conception.

**Modules principaux :**
- `app/api/`
- `app/chat/`
- `app/synthesis/`
- `ui/`

### WS7 - Claims, preuves, contradictions et synthèse approfondie

**Objectif :** construire la couche d'analyse auditable au-dessus des passages documentaires.

**Responsabilités :**
- extraction atomique d'affirmations ;
- canonicalisation ;
- vérification indépendante ;
- liens de preuves ;
- relations de support, contradiction, dépendance et généralisation ;
- évaluation de qualité des preuves ;
- planificateur de recherche approfondie ;
- synthèse multi-sources traçable ;
- abstention explicite si preuves insuffisantes.

**Modules principaux :**
- `app/claims/`
- `app/synthesis/`
- `app/research/`

### WS8 - Stratégies candidates, calculs et backtests

**Objectif :** transformer les résultats documentaires en spécifications de stratégies testables, puis exécuter des backtests reproductibles.

**Responsabilités :**
- compilateur de stratégie YAML ;
- attribution obligatoire de l'origine de chaque règle ;
- moteur de contraintes ;
- génération ou assemblage de code déterministe ;
- contrôle des biais ;
- registre append-only des expériences ;
- stockage des résultats négatifs ;
- validation hors échantillon, walk-forward et stress tests.

**Modules principaux :**
- `app/strategies/`
- `app/backtests/`
- `data/experiments/`

### WS9 - Évaluation, qualité, observabilité et exploitation

**Objectif :** mesurer, surveiller et durcir le système avant acceptation V1.

**Responsabilités :**
- corpus pilote de 50 à 100 PDF ;
- jeu annoté page par page ;
- benchmark routes documentaires ;
- benchmark LLM principal ;
- benchmark recherche ;
- benchmark réponses ;
- logs structurés ;
- métriques ingestion, recherche, claims et réponses ;
- sauvegardes chiffrées ;
- documentation d'exploitation locale.

**Modules principaux :**
- `evaluation/`
- `tests/`
- `data/logs/`
- `docs/operations/`

---

## 3. Milestones

### M0 - Cadrage exécutable et squelette projet

**But :** passer d'une spécification à un projet exécutable localement.

**Workstreams actifs :** WS0, WS1, WS2, WS9

**Livrables :**
- arborescence conforme à la spécification ;
- `pyproject.toml` ;
- configuration initiale dans `config/` ;
- schémas de base dans `schemas/` ;
- conventions d'erreurs et de statuts ;
- squelette FastAPI ;
- squelette workers ;
- suite de tests minimale ;
- matrice initiale de conformité V1.

**Critère d'acceptation :**
- le projet s'installe localement ;
- les tests de smoke passent ;
- les services peuvent démarrer sans exposer de port public ;
- les statuts d'erreur sont explicites, sans fallback silencieux.

**Dépendances :** aucune.

### M1 - Socle de persistance, jobs et API interne

**But :** disposer d'une base persistante et d'un orchestrateur idempotent.

**Workstreams actifs :** WS1, WS2, WS9

**Livrables :**
- PostgreSQL avec migrations ;
- tables documents, pages, conversions, jobs, conversations, turns ;
- Qdrant lancé localement ;
- file de jobs avec types et priorités de la spécification ;
- idempotence par hash d'entrée, configuration, code et modèle ;
- logs structurés avec `trace_id`, `job_id`, phase, statut et latence ;
- endpoints de santé et readiness.

**Critère d'acceptation :**
- un job rejoué avec les mêmes entrées n'est pas recalculé sans option explicite ;
- les ports sont liés à `127.0.0.1` ;
- les erreurs de configuration bloquent le démarrage avec message actionnable ;
- les migrations sont reproductibles depuis une base vide.

**Dépendances :** M0.

### M2 - Inventaire, diagnostic et routage PDF

**But :** identifier chaque PDF, diagnostiquer chaque page et produire une route documentaire explicite.

**Workstreams actifs :** WS2, WS3, WS9

**Livrables :**
- endpoint `POST /v1/documents` ;
- endpoint `POST /v1/documents/{document_id}/diagnose` ;
- enregistrement `DocumentRecord` ;
- enregistrement `PageDiagnostic` ;
- machine d'états documentaire jusqu'à `ROUTE_PLANNED`, `MANUAL_REVIEW` ou `QUARANTINED` ;
- implémentation de `routing.yaml` ;
- rapport de diagnostic par document ;
- premiers tests sur corpus synthétique.

**Critère d'acceptation :**
- 100 % des PDF inventoriés ont un identifiant stable ;
- aucun original n'est modifié ;
- chaque page diagnostiquée a un état, une confiance et une route recommandée ;
- une route incertaine ne bascule pas vers une autre route : elle passe en revue explicite ;
- les documents en quarantaine ne sont pas indexables.

**Dépendances :** M1.

### M3 - Conversion hybride et DoclingDocument canonique

**But :** convertir les documents pilotes en JSON Docling valide et traçable.

**Workstreams actifs :** WS3, WS4, WS9

**Livrables :**
- endpoint `POST /v1/documents/{document_id}/convert` ;
- profil Docling standard ;
- profil Granite-Docling ;
- rendu de pages ;
- prétraitement OCRmyPDF conditionnel ;
- fusion pagewise ;
- `ConversionRun` ;
- stockage `corpus/docling/` ;
- exports régénérables ;
- QA post-conversion ;
- quarantaine explicite.

**Critère d'acceptation :**
- le nombre de pages correspond au PDF original ;
- le JSON Docling est valide ;
- chaque `DocItemRecord` contient page, route, autorité textuelle et provenance ;
- aucune page n'est silencieusement omise ;
- les PDF mixtes conservent la pagination ;
- les documents qui échouent au QA ne passent pas à l'indexation.

**Dépendances :** M2.

### M4 - Chunking, indexation et recherche citée

**But :** rendre un corpus pilote consultable avec recherche hybride et références ouvrables.

**Workstreams actifs :** WS5, WS9

**Livrables :**
- endpoint `POST /v1/documents/{document_id}/index` ;
- chunking hiérarchique ;
- enrichissement de métadonnées ;
- embeddings denses ;
- BM25 ou sparse Qdrant ;
- collection Qdrant avec payload complet ;
- indexation incrémentale d'un document ajouté après l'initialisation du corpus ;
- fusion dense/sparse ;
- reranking ;
- endpoint `POST /v1/search` ;
- format interne de citation ;
- évaluation retrieval initiale.

**Critère d'acceptation :**
- chaque chunk remonte à ses `item_ids` et pages ;
- les filtres de métadonnées fonctionnent ;
- une recherche renvoie citations, scores et provenance ;
- Recall@20 est mesuré sur un premier jeu annoté ;
- les documents en quarantaine sont absents de l'index ;
- un PDF ajouté après le premier corpus peut être inventorié, converti, validé et indexé sans retraiter les documents inchangés ;
- une erreur d'embedding ou de reranking produit un statut explicite.

**Dépendances :** M3.

### M5 - Chatbot MVP avec conversations et citations

**But :** livrer la première tranche verticale produit : poser une question, obtenir une réponse citée, poursuivre la conversation.

**Workstreams actifs :** WS1, WS5, WS6, WS9

**Livrables :**
- endpoint `POST /v1/conversations` ;
- endpoint `GET /v1/conversations/{conversation_id}` ;
- endpoint `GET /v1/conversations/{conversation_id}/turns` ;
- endpoint `POST /v1/conversations/{conversation_id}/messages` ;
- endpoint `POST /v1/chat/completions` ;
- classification de requête initiale ;
- résolution des références conversationnelles simples ;
- assemblage de preuves ;
- génération structurée par Gemma via vLLM ;
- vérification minimale des citations ;
- UI locale de chat ;
- affichage du statut documentaire.

**Critère d'acceptation :**
- l'utilisateur peut créer une conversation ;
- une question de suivi reprend le contexte utile du tour précédent ;
- chaque réponse factuelle affiche au moins une preuve ouvrable ;
- un PDF acquis après la mise en service du MVP peut devenir interrogeable après passage explicite par inventaire, diagnostic, conversion, QA et indexation ;
- le statut `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE` ou `REQUIRES_CURRENT_DATA` est visible ;
- l'historique conversationnel n'est pas traité comme source factuelle ;
- si les preuves manquent, le chatbot s'abstient explicitement.

**Dépendances :** M4.

### M6 - Claims, vérification et recherche approfondie

**But :** ajouter la couche d'analyse multi-sources auditable.

**Workstreams actifs :** WS6, WS7, WS9

**Livrables :**
- endpoint `POST /v1/claims/extract` ;
- endpoint `POST /v1/claims/{claim_id}/verify` ;
- endpoints `GET /v1/claims/{claim_id}` et `/evidence` ;
- extraction atomique structurée ;
- vérification entailment ;
- relations entre claims ;
- détection de contradictions ;
- évaluation de qualité des preuves ;
- endpoint `POST /v1/research/deep` ;
- planificateur de recherche multi-requêtes ;
- synthèse approfondie avec convergences, contradictions, limites et conditions.

**Critère d'acceptation :**
- une affirmation sans preuve n'est pas promue en claim vérifié ;
- conditions, limites et dépendances sont conservées ;
- les contradictions sont explicites ;
- la synthèse distingue source, déduction et choix de conception ;
- la couverture documentaire est mesurée ;
- les citations restent ouvrables depuis la réponse finale.

**Dépendances :** M5.

### M7 - Stratégies candidates et backtests reproductibles

**But :** compiler des stratégies candidates issues des sources et les tester par code déterministe.

**Workstreams actifs :** WS7, WS8, WS9

**Livrables :**
- endpoint `POST /v1/strategies/compile` ;
- endpoint `GET /v1/strategies/{strategy_id}` ;
- schéma YAML de stratégie candidate ;
- attribution obligatoire `SOURCE`, `DEDUCTION`, `DESIGN_CHOICE`, `PARAMETER_TO_CALIBRATE`, `USER_CONSTRAINT` ;
- moteur de contraintes ;
- endpoint `POST /v1/strategies/{strategy_id}/backtest` ;
- endpoint `GET /v1/experiments/{experiment_id}` ;
- registre append-only des expériences ;
- contrôles biais, coûts, liquidité, stabilité et benchmarks simples ;
- rapports de backtest cités et reproductibles.

**Critère d'acceptation :**
- une stratégie candidate contient des règles déterministes ;
- chaque règle indique son origine ;
- aucun paramètre inventé par le LLM n'est accepté sans statut explicite ;
- le LLM ne calcule pas mentalement les résultats ;
- les résultats négatifs sont conservés ;
- un backtest peut être reproduit depuis `spec_hash`, `data_snapshot`, paramètres et modèle de coût.

**Dépendances :** M6.

### M8 - Évaluation pilote et calibration

**But :** mesurer la qualité du système sur un corpus pilote représentatif avant durcissement V1.

**Workstreams actifs :** WS0, WS3, WS4, WS5, WS6, WS7, WS8, WS9

**Livrables :**
- corpus pilote de 50 à 100 PDF ;
- jeu annoté page par page ;
- benchmark routes documentaires ;
- benchmark LLM principal ;
- benchmark recherche sur 100 à 300 questions ;
- benchmark réponses ;
- seuils calibrés dans `routing.yaml` et `quality_gates.yaml` ;
- rapport de calibration ;
- liste des écarts bloquants V1.

**Critère d'acceptation :**
- les métriques de conversion sont mesurées : CER/WER, exactitude numérique, signes, tableaux, ordre de lecture ;
- les modèles Gemma candidats sont comparés sur tâches métier ;
- Recall@5, Recall@10, Recall@20, MRR et nDCG sont publiés ;
- précision des citations et taux d'abstention sont mesurés ;
- aucun modèle communautaire n'est promu sans benchmark supérieur ou égal aux références ;
- les seuils de routage sont justifiés par données.

**Dépendances :** M7 peut être partiel si l'évaluation backtest n'est pas encore complète, mais M5 et M6 doivent être stables.

### M9 - Durcissement, exploitation et acceptation V1

**But :** transformer le prototype complet en version personnelle exploitable et maintenable.

**Workstreams actifs :** WS0, WS1, WS6, WS8, WS9

**Livrables :**
- durcissement sécurité ;
- vérification ports locaux ;
- sauvegardes chiffrées ;
- runbooks d'exploitation ;
- monitoring local ;
- tests de régression ;
- tests de restauration ;
- optimisation mémoire DGX Spark ;
- documentation utilisateur ;
- rapport final d'acceptation V1.

**Critère d'acceptation :**
- les 20 critères d'acceptation V1 de la spécification sont validés ou marqués explicitement non satisfaits ;
- aucun service n'est exposé publiquement ;
- les sauvegardes sont restaurées au moins une fois en test ;
- les profils de charge évitent les pics simultanés inutiles ;
- la suite de régression couvre ingestion, recherche, chat, claims, stratégies et backtests ;
- les anti-patterns interdits sont vérifiés par revue ou tests automatisés lorsque possible.

**Dépendances :** M8.

---

## 4. Chemin critique

Le chemin critique minimal pour atteindre un chatbot cité est :

```text
M0 Squelette
-> M1 Persistance et jobs
-> M2 Inventaire / diagnostic / routage
-> M3 Conversion Docling canonique
-> M4 Indexation hybride
-> M5 Chatbot avec citations
```

Le chemin critique pour la version complète V1 est :

```text
M5 Chatbot cité
-> M6 Claims et recherche approfondie
-> M7 Stratégies et backtests
-> M8 Évaluation pilote
-> M9 Durcissement V1
```

---

## 5. Mapping spécification vers milestones

| Spécification | Milestone principal | Workstreams |
|---|---|---|
| ADR et principes d'architecture | M0 | WS0 |
| Services DGX Spark et profils de charge | M1, M9 | WS1 |
| Organisation des données | M0, M1 | WS2 |
| Modèles de données | M1 | WS2 |
| Machine d'états documentaire | M2 | WS2, WS3 |
| Phase 0 - Ingestion et inventaire | M2 | WS3 |
| Phase 1 - Diagnostic page par page | M2 | WS3 |
| Phase 2 - Routage du document | M2 | WS3 |
| Phase 3 - Contrôle qualité pré-conversion | M3 | WS4 |
| Phase 4 - Conversion structurée | M3 | WS4 |
| Phase 5 - Contrôle qualité post-conversion | M3 | WS4 |
| Phase 6 - Chunking hiérarchique | M4 | WS5 |
| Phase 7 - Enrichissement des métadonnées | M4 | WS5 |
| Phase 8 - Embeddings et indexation | M4 | WS5 |
| Couche conversationnelle | M5 | WS6 |
| Phase 9 - Recherche et preuves | M5, M6 | WS5, WS6, WS7 |
| Phase 10 - Registre d'affirmations | M6 | WS7 |
| Phase 11 - Qualité des preuves | M6 | WS7 |
| Phase 12 - Contradictions | M6 | WS7 |
| Phase 13 - Synthèse multi-sources | M6 | WS7 |
| Phase 14 - Stratégie candidate | M7 | WS8 |
| Phase 15 - Backtest et validation | M7 | WS8 |
| Phase 16 - Vérification des réponses | M5, M6 | WS6, WS7 |
| API fonctionnelle | M2 à M7 | WS6 |
| Configuration indicative | M0, M1, M8 | WS0, WS1, WS9 |
| Orchestration | M1 | WS1 |
| Observabilité et audit | M1, M9 | WS9 |
| Sécurité et confidentialité | M1, M9 | WS1, WS9 |
| Plan d'évaluation | M8 | WS9 |
| Critères d'acceptation V1 | M9 | WS0, WS9 |

---

## 6. Ordre de réalisation recommandé

1. **Construire la tranche verticale documentaire avant les fonctions avancées.** Le chatbot sans provenance fiable ne satisfait pas la spécification.
2. **Faire fonctionner le pipeline sur un corpus minuscule.** Commencer avec 3 à 5 PDF représentatifs avant le corpus pilote complet.
3. **Mesurer tôt les routes documentaires.** Le choix Docling standard, Granite-Docling ou prétraitement conditionnel détermine la qualité de tout le reste.
4. **Stabiliser les citations avant la synthèse profonde.** Les claims et contradictions dépendent de liens de preuves corrects.
5. **Ajouter les stratégies après les claims vérifiés.** Une stratégie candidate doit être issue de preuves structurées, pas seulement d'une réponse textuelle.
6. **Durcir en continu.** Sécurité locale, absence d'exposition publique, logs et idempotence doivent être présents dès les premiers services.

---

## 7. Définition d'achèvement transverse

Un développement est considéré terminé seulement si :

- le comportement est couvert par tests unitaires ou d'intégration adaptés au risque ;
- les erreurs attendues ont des statuts explicites ;
- aucune bascule silencieuse n'est introduite ;
- les artefacts persistants sont idempotents ou versionnés ;
- les logs contiennent assez de contexte pour auditer le traitement ;
- la provenance est conservée lorsqu'un contenu documentaire est manipulé ;
- les endpoints publics locaux sont documentés ;
- les critères de sécurité locale restent validés ;
- la matrice de conformité est mise à jour.

---

## 8. Risques principaux et contrôles

| Risque | Contrôle |
|---|---|
| Mauvaise conversion de chiffres, signes ou tableaux | QA post-conversion, jeu annoté, métriques numériques strictes |
| Route documentaire incorrecte | Diagnostic page par page, seuils calibrés, revue explicite si confiance insuffisante |
| Citations fausses ou non ouvrables | `item_id`, page PDF, bbox, vérification de réponse |
| Hallucination de synthèse | registre de claims, entailment, abstention explicite |
| Paramètres de stratégie inventés | origine obligatoire des règles, `PARAMETER_TO_CALIBRATE` |
| Backtest biaisé | contrôles survivance, look-ahead, coûts, liquidité, walk-forward |
| Explosion mémoire sur DGX Spark | profils de charge, concurrence limitée, benchmarks |
| Exposition réseau accidentelle | bind `127.0.0.1`, tests de configuration, revue sécurité |
| Résultats non reproductibles | hashes, versions modèle/code/config, registre append-only |

---

## 9. Jalons de décision

### D1 - Choix des seuils de routage

**Moment :** fin M2, puis recalibration M8.  
**Décision :** seuils `routing.yaml` pour routes natives, scans, prétraitement et enrichissement ciblé.  
**Données requises :** diagnostics pages, échantillon annoté, erreurs observées.

### D2 - Promotion du pipeline de conversion

**Moment :** fin M3.  
**Décision :** routes autorisées pour ingestion batch.  
**Données requises :** QA structurelle, exactitude numérique, fidélité tableaux, temps par page.

### D3 - Choix embeddings et reranker

**Moment :** fin M4.  
**Décision :** modèles d'embedding et de reranking retenus.  
**Données requises :** Recall@k, MRR, nDCG, performance FR vers sources EN.

### D4 - Promotion du modèle LLM principal

**Moment :** M5 pour MVP, M8 pour V1.  
**Décision :** modèle Gemma principal et paramètres de contexte.  
**Données requises :** JSON valide, tool calling, négations, nombres, citations, entailment.

### D5 - Acceptation des stratégies et backtests en V1

**Moment :** fin M7.  
**Décision :** périmètre exact des stratégies compilées et des backtests autorisés.  
**Données requises :** reproductibilité, contrôles biais, registre d'expériences, tests déterministes.

---

## 10. Livrable V1 attendu

À la fin de M9, le système doit permettre :

- de charger une bibliothèque personnelle de PDF ;
- d'inventorier, diagnostiquer, router, convertir, valider et indexer les documents ;
- de poser des questions en français ou en anglais dans une interface de chat locale ;
- de poursuivre une conversation avec contexte utile ;
- de recevoir des réponses citées et ouvrables ;
- de lancer une recherche approfondie multi-sources ;
- de consulter claims, preuves, contradictions et limites ;
- de compiler une stratégie candidate avec origine explicite de chaque règle ;
- d'exécuter un backtest reproductible par code déterministe ;
- de conserver les expériences positives et négatives ;
- d'auditer les traitements, configurations, modèles et versions utilisés ;
- d'exploiter le tout localement sans exposition publique.
