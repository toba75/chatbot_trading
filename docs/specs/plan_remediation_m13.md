# Plan de remédiation M13 - validation réelle bout-en-bout

## Milestone

- Nom: M13-remediation - Validation réelle du pipeline produit.
- Source: reprise de la tranche `M13-reality`, spécification v4.1, plan d'implémentation M-012/M-013 et rapport des écarts V1 M-012.
- Objectif métier: faire correspondre le mot "réel" à la vraie vie du produit: PDF réels en entrée, pipeline documentaire réel, recherche réelle, réponse conversationnelle citée réelle, appel Gemma réel via Spark, puis preuve ouvrable jusqu'au PDF original.

Le périmètre M13-reality déjà livré doit être requalifié comme smoke test LLM live. Il prouve que `orchestrator-api -> llm-gateway -> Spark/vLLM` fonctionne, mais il ne prouve pas que le chatbot trading fonctionne sur des PDF réels ni que les évaluations traversent la chaîne documentaire.

## Définition De "Réel"

Un test est réel uniquement s'il traverse la chaîne suivante sans substitution:

```text
PDF original réel
-> enregistrement Source Processing
-> diagnostic page par page
-> conversion Docling, Granite-Docling ou OCRmyPDF selon route explicite
-> contrôle qualité documentaire
-> version canonique publiée
-> chunking et projection de connaissance
-> index hybride réel
-> recherche Knowledge Access réelle
-> assemblage et scellement des preuves Research Answering
-> appel Gemma via llm-gateway
-> vérification des assertions et citations
-> réponse conversationnelle avec citations ouvrables
-> ouverture de la preuve vers PDF, page et fragment source
```

## Interdictions

Ces éléments rendent un test non réel et doivent faire échouer les gates de remédiation:

- mock, stub, fake provider ou adapter mémoire de substitution sur le chemin d'acceptation bout-en-bout;
- prompt codé en dur présenté comme donnée documentaire;
- PDF synthétique généré par le test;
- corpus fixture utilisé comme remplacement du corpus réel;
- résultat RA, KA, EG, CV, SD ou EX préfabriqué;
- citation artificielle comme `SRC-M013-1` sans PDF, page et fragment résolubles;
- réponse LLM publiée sans preuve documentaire lorsque la question exige une preuve;
- fallback vers un modèle, une recherche vide, un résultat en mémoire ou une réponse générique;
- succès logiciel qui masque un échec scientifique.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded contexts concernés: `source_processing`, `knowledge_access`, `evidence_governance`, `research_answering`, `conversation`, `strategy_design`, `experimentation`, `evaluation`, `platform`.
- Objectif métier: accepter la V1 seulement si une question utilisateur peut partir d'un corpus PDF réel et produire une réponse vérifiée, qualifiée ou abstinente avec preuve ouvrable.
- Langage ubiquitaire: corpus réel, manifeste de corpus, PDF original immuable, version canonique, route documentaire, projection de connaissance, preuve candidate, claim vérifié, réponse vérifiée, conversation locale, citation ouvrable, stratégie candidate, expérience reproductible, absence de fallback.
- Invariants critiques: chaque preuve remonte au PDF original; aucune page n'est omise silencieusement; chaque réponse factuelle est supportée, qualifiée ou explicitement refusée; une panne d'outil réel bloque le scénario concerné au lieu de déclencher un remplacement.
- Garde-fous: aucun mode dégradé implicite; aucun statut GREEN sans PDF local résolvable; aucune dépendance directe du navigateur, de CV, RA ou EV vers Spark hors `llm-gateway`.

## Blocages Ou Prérequis

- État GREEN/RED connu: le chemin LLM live M13 est GREEN, mais le pipeline produit réel bout-en-bout n'est pas prouvé.
- Présence des milestones amont dans master: à revérifier avant implémentation avec `git fetch origin --prune` puis inspection de `master` pour M-003 à M-013.
- Décisions manquantes: créer une ADR si l'exécution réelle bout-en-bout introduit un nouveau mode d'exploitation local, un format de manifeste de corpus privé ou une règle de stockage non couverte par les ADR existantes.
- Risques: absence de corpus local, dépendance à des chemins machine, durée longue des conversions, indisponibilité Spark, Qdrant ou Docling, confusion entre test de contrat et test produit réel.

## Definition Of Done

La remédiation est terminée seulement si:

- un corpus local de vrais PDF est déclaré par manifeste strict;
- au moins un scénario documentaire complet part d'un PDF réel et retourne une réponse citée ouvrable;
- au moins un scénario de recherche échoue explicitement si la bonne page n'est pas retrouvée;
- au moins un scénario conversationnel passe par `/v1/chat/completions` sans contourner CV, RA, KA, EG ni `llm-gateway`;
- au moins un scénario stratégie/backtest refuse explicitement la production si les preuves ou données de marché réelles manquent;
- `scripts/validate_m013_reality.ps1` ne peut plus être GREEN avec les seuls micro-prompts LLM;
- le rapport V1 distingue les preuves réelles bout-en-bout des smoke tests techniques.

## Tâches

### T-001 - Requalifier M13-reality en smoke test LLM live

- But métier: supprimer l'ambiguïté entre chemin LLM réel et pipeline produit réel.
- Portée DDD: documentation de M-013, traçabilité, rapport V1, langage de gate.
- Scénario BDD:
  - Given le validateur actuel M13 appelle Gemma réel avec des micro-prompts.
  - When le rapport d'acceptation décrit la preuve obtenue.
  - Then il la qualifie comme smoke test LLM live et non comme validation réelle du produit.
- Tests d'acceptation à écrire: un validateur documentaire qui échoue si `M13-reality` est présenté comme preuve de pipeline PDF bout-en-bout.
- Tests unitaires à écrire: contrôle des libellés dans le rapport V1, la matrice de traçabilité et le journal M-013.
- Implémentation attendue: renommer les preuves existantes dans la documentation sans supprimer leur valeur technique.
- Invariants et garde-fous: ne pas changer le sens d'une ADR acceptée; ne pas masquer l'écart produit.
- Dépendances: `docs/tasks/milestone_013/0013_ancrer_gateway_llm_chemin_reel.md`, `docs/traceability/matrix.md`, rapport V1.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_traceability.ps1`.
- Commit RED: `test(m013): refuser confusion smoke llm et pipeline reel`.
- Commit GREEN: `docs(m013): requalifier reality en smoke test llm live`.

### T-002 - Déclarer le corpus réel local obligatoire

- But métier: rendre impossible une validation réelle sans PDF réels.
- Portée DDD: EV, SP, manifeste de corpus, références vers originaux locaux.
- Scénario BDD:
  - Given l'utilisateur déclare un corpus local de PDF trading et investissement.
  - When le gate de réalité charge le manifeste.
  - Then chaque PDF existe, possède un hash stable, une strate documentaire et une justification d'inclusion.
- Tests d'acceptation à écrire: `tests/m013/validate_real_corpus_manifest_acceptance.ps1`.
- Tests unitaires à écrire: manifest absent, chemin non résolvable, hash manquant, strate absente, doublon binaire, document hors plage 50-100, exclusion non justifiée.
- Implémentation attendue: créer un format strict de manifeste local, par exemple `docs/evaluation/m013/real_corpus_manifest.schema.json`, et un validateur qui lit le chemin du manifeste depuis `config/application.yaml` sans accepter de variable d'environnement.
- Invariants et garde-fous: aucun PDF généré; aucun chemin par défaut; aucun corpus minimal de secours; aucun original modifié.
- Dépendances: exigences M-012 de corpus pilote et strates documentaires.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_corpus_manifest_acceptance.ps1`.
- Commit RED: `test(m013): exiger manifeste corpus reel`.
- Commit GREEN: `feat(m013): valider manifeste corpus reel`.

### T-003 - Publier le jeu annoté réel de questions et preuves attendues

- But métier: évaluer le produit sur des questions dont les preuves attendues sont connues.
- Portée DDD: EV, RA, KA, SP, annotations page par page.
- Scénario BDD:
  - Given un corpus réel est déclaré.
  - When un jeu d'évaluation référence ses questions.
  - Then chaque question possède des pages attendues, fragments attendus, assertions attendues et statut documentaire attendu.
- Tests d'acceptation à écrire: `tests/m013/validate_real_question_set_acceptance.ps1`.
- Tests unitaires à écrire: question sans PDF, page hors borne, fragment absent, assertion sans statut, citation non résoluble, question stratégie sans preuve exigée.
- Implémentation attendue: créer un format strict de jeu annoté local, sans contenu PDF complet en Git si les PDF restent privés.
- Invariants et garde-fous: aucune question synthétique cachée dans le code; aucune citation artificielle; aucun succès si une annotation attendue manque.
- Dépendances: T-002.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_question_set_acceptance.ps1`.
- Commit RED: `test(m013): exiger questions annotees reelles`.
- Commit GREEN: `feat(m013): valider jeu annote reel`.

### T-004 - Exécuter réellement Source Processing sur les PDF

- But métier: prouver que les PDF réels deviennent des versions canoniques traçables.
- Portée DDD: SP, `SourceDocument`, diagnostic, route de page, artefacts Docling, contrôle qualité.
- Scénario BDD:
  - Given un PDF réel du manifeste.
  - When le pipeline SP le traite.
  - Then chaque page reçoit une route explicite, un artefact canonique ou une quarantaine, et la pagination d'origine reste traçable.
- Tests d'acceptation à écrire: `tests/m013/validate_real_source_processing_acceptance.ps1`.
- Tests unitaires à écrire: original modifié, page omise, route absente, Docling JSON absent, OCRmyPDF appliqué sans condition, quarantaine non explicite, hash canonique absent.
- Implémentation attendue: brancher le runtime local sur les vrais adaptateurs Docling, Granite-Docling et OCRmyPDF conditionnel ou échouer explicitement si l'outil requis est absent.
- Invariants et garde-fous: pas de conversion fixture; pas de page ignorée; pas de route par défaut; pas d'OCR global.
- Dépendances: T-002, T-003, ADR Docling/OCR existantes.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_source_processing_acceptance.ps1`.
- Commit RED: `test(m013): couvrir traitement pdf reel`.
- Commit GREEN: `feat(m013): traiter corpus pdf reel`.

### T-005 - Construire et interroger une projection KA réelle

- But métier: prouver que la recherche retrouve les bonnes pages depuis les versions canoniques.
- Portée DDD: KA, projection de connaissance, embeddings, index hybride, reranking, provenance.
- Scénario BDD:
  - Given une version canonique publiée d'un PDF réel.
  - When KA construit l'index et exécute les questions annotées.
  - Then les candidats retournés portent un `SourceLocator` résoluble et le rappel attendu est mesuré.
- Tests d'acceptation à écrire: `tests/m013/validate_real_knowledge_search_acceptance.ps1`.
- Tests unitaires à écrire: projection absente, index stale, candidat sans locator, score sans trace, page attendue non retrouvée, Qdrant indisponible.
- Implémentation attendue: brancher l'exécution de gate sur l'index réel et les services réels d'embedding/reranking déclarés dans la topologie locale.
- Invariants et garde-fous: pas d'`InMemoryHybridSearch` dans le gate réel; pas de succès vide; pas de candidat sans provenance ouvrable.
- Dépendances: T-004, services d'indexation locaux.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_knowledge_search_acceptance.ps1`.
- Commit RED: `test(m013): couvrir recherche reelle sur corpus`.
- Commit GREEN: `feat(m013): interroger projection reelle`.

### T-006 - Produire une réponse RA réelle fondée sur preuves

- But métier: prouver qu'une réponse factuelle ne sort que si les preuves du corpus réel la supportent.
- Portée DDD: RA, EG, preuves scellées, claims, statuts documentaires.
- Scénario BDD:
  - Given une question annotée possède des preuves attendues dans le corpus réel.
  - When RA répond à la question.
  - Then la réponse est supportée, partiellement supportée, conflictuelle ou abstinente selon les preuves réelles, avec citations ouvrables.
- Tests d'acceptation à écrire: `tests/m013/validate_real_verified_answer_acceptance.ps1`.
- Tests unitaires à écrire: assertion non supportée, citation absente, citation non ouvrable, obligation de recherche manquante, contradiction ignorée, abstention attendue non produite.
- Implémentation attendue: orchestrer RA avec KA réel, EG réel et `llm-gateway` réel pour la génération, puis vérifier les assertions avant publication.
- Invariants et garde-fous: aucune réponse plausible sans preuve; aucun fallback vers mémoire conversationnelle; aucun statut documentaire inventé.
- Dépendances: T-005, `llm-gateway`, Spark.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_verified_answer_acceptance.ps1`.
- Commit RED: `test(m013): couvrir reponse verifiee reelle`.
- Commit GREEN: `feat(m013): produire reponse reelle citee`.

### T-007 - Valider le chat produit réel

- But métier: prouver que l'utilisateur interagit avec le pipeline réel via le contrat conversationnel.
- Portée DDD: CV, RA, KA, EG, platform, endpoint `/v1/chat/completions`.
- Scénario BDD:
  - Given un utilisateur pose une question en langage naturel dans une conversation locale.
  - When `/v1/chat/completions` traite la demande.
  - Then le tour CV est créé, le mode est justifié, RA récupère les preuves réelles, Gemma répond via `llm-gateway`, et la réponse expose les citations ouvrables.
- Tests d'acceptation à écrire: `tests/m013/validate_real_chat_pipeline_acceptance.ps1`.
- Tests unitaires à écrire: conversation absente, idempotence absente, mode injustifié, RA contourné, citation non exposée, Spark appelé directement.
- Implémentation attendue: relier l'orchestrateur local au vrai handler CV et à ses ports applicatifs au lieu d'un endpoint chat simplifié limité au LLM.
- Invariants et garde-fous: pas de chat générique; pas de réponse sans tour CV; pas de prompt produit codé en dur comme preuve; pas d'accès direct à Spark.
- Dépendances: T-006, endpoint CV M-008.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_chat_pipeline_acceptance.ps1`.
- Commit RED: `test(m013): couvrir chat pipeline reel`.
- Commit GREEN: `feat(m013): brancher chat produit sur pipeline reel`.

### T-008 - Vérifier les scénarios stratégie et backtest sans substitution

- But métier: empêcher une réponse générique sur les stratégies de trading lorsque la preuve, la calibration ou les données réelles manquent.
- Portée DDD: SD, EX, RA, EG, CV.
- Scénario BDD:
  - Given l'utilisateur demande "Quelle est la meilleure stratégie Short possible ?"
  - When le chatbot route la demande vers stratégie.
  - Then le système recherche les preuves réelles, propose uniquement des règles sourcées, refuse les paramètres non calibrés, et lance un backtest seulement si les données de marché versionnées sont disponibles.
- Tests d'acceptation à écrire: `tests/m013/validate_real_strategy_short_acceptance.ps1`.
- Tests unitaires à écrire: règle sans origine, paramètre sans calibration, donnée de marché absente, backtest non déterministe, résultat négatif supprimé, réponse générique non sourcée.
- Implémentation attendue: relier CV vers SD/EX via les façades existantes et publier un diagnostic explicite lorsque le pipeline réel ne dispose pas des preuves ou données nécessaires.
- Invariants et garde-fous: pas de conseil stratégique non sourcé; pas de "meilleure stratégie" universelle inventée; pas de backtest sur données fictives.
- Dépendances: T-007, modules SD et EX M-010/M-011.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_strategy_short_acceptance.ps1`.
- Commit RED: `test(m013): couvrir strategie short reelle`.
- Commit GREEN: `feat(m013): refuser strategie non prouvee`.

### T-009 - Publier le rapport d'exécution réelle

- But métier: rendre auditable chaque run réel du pipeline.
- Portée DDD: EV, observabilité, gouvernance V1.
- Scénario BDD:
  - Given un run réel exécute corpus, recherche, réponse, chat et éventuellement stratégie.
  - When le run se termine.
  - Then un rapport conserve les identifiants, hashes, versions d'outils, métriques, citations et échecs sans stocker de secrets ni payloads sensibles complets.
- Tests d'acceptation à écrire: `tests/m013/validate_real_pipeline_report_acceptance.ps1`.
- Tests unitaires à écrire: version outil absente, hash PDF absent, citation non listée, métrique obligatoire absente, secret présent, échec non reporté.
- Implémentation attendue: produire `docs/evaluation/m013/real_pipeline_run_report.md` ou un artefact local équivalent contrôlé par gate.
- Invariants et garde-fous: aucun rapport GREEN sans run; aucun secret; aucun prompt complet; aucune correction manuelle des résultats.
- Dépendances: T-002 à T-008.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_pipeline_report_acceptance.ps1`.
- Commit RED: `test(m013): couvrir rapport pipeline reel`.
- Commit GREEN: `docs(m013): publier rapport pipeline reel`.

### T-010 - Rendre l'acceptation V1 dépendante du pipeline réel

- But métier: empêcher l'acceptation V1 si seul le smoke test LLM est GREEN.
- Portée DDD: M-013, gates, traçabilité, rapport d'acceptation V1.
- Scénario BDD:
  - Given les smoke tests techniques sont GREEN mais le pipeline PDF réel n'a pas été exécuté.
  - When le gate M-013 d'acceptation est lancé.
  - Then le gate échoue avec un diagnostic explicite.
- Tests d'acceptation à écrire: `tests/m013/validate_real_pipeline_gate_acceptance.ps1`.
- Tests unitaires à écrire: script M-013 sans gate E2E, rapport V1 sans run réel, matrice de traçabilité sans preuve E2E, smoke test utilisé comme preuve produit.
- Implémentation attendue: faire appeler les validations T-002 à T-009 par `scripts/validate_m013_reality.ps1` ou créer `scripts/validate_m013_real_pipeline.ps1` puis l'enrôler dans `scripts/test.ps1` et le rapport V1.
- Invariants et garde-fous: aucun fallback vers le validateur LLM seul; aucun opt-out silencieux; tout prérequis absent échoue avec erreur nommée.
- Dépendances: T-009.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_real_pipeline.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): rendre pipeline reel bloquant`.
- Commit GREEN: `chore(m013): bloquer acceptation sans pipeline reel`.

## Séquence D'Exécution Recommandée

1. Geler l'ambiguïté documentaire avec T-001.
2. Rendre les entrées réelles obligatoires avec T-002 et T-003.
3. Faire passer SP, KA et RA sur le corpus réel avec T-004 à T-006.
4. Brancher CV et `/v1/chat/completions` sur ce chemin avec T-007.
5. Couvrir le cas stratégie/backtest avec T-008.
6. Publier les preuves de run avec T-009.
7. Rendre le gate V1 bloquant avec T-010.

## Commande Cible Finale

La commande finale ne doit être GREEN que si le pipeline complet a réellement tourné:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_m013_real_pipeline.ps1
```

Elle doit échouer explicitement si le corpus réel, Docling, Granite-Docling, OCRmyPDF requis, Qdrant, embeddings, reranker, `llm-gateway`, Spark ou les données de marché requises sont indisponibles.
