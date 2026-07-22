# Plan d'implémentation v4.1 - Milestones et Workstreams

Source unique: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`.

Date de création: 21 juin 2026.

Statut: plan initial d'implémentation.

Ce document repart de zéro depuis la spécification v4.1. Il ne reprend pas un plan antérieur comme source. Toute modification structurante ultérieure devra être documentée par ADR dans `docs/adr/` et reportée dans `docs/adr/index.md`.

## 1. Intention métier

Le système doit transformer un corpus financier hétérogène en connaissances vérifiables, puis produire des réponses conversationnelles citées, des synthèses conditionnelles, des stratégies candidates attribuées et des expériences reproductibles.

La chaîne métier directrice est:

```text
Document source
-> Version canonique
-> Preuve localisable
-> Affirmation vérifiée
-> Réponse ou synthèse vérifiée
-> Stratégie candidate attribuée
-> Expérience reproductible
-> Résultat interprétable et conservé
```

Les jalons sont donc ordonnés par capacité métier vérifiable, pas par composant technique isolé.

## 2. Règles d'exécution

Chaque milestone doit être exécuté selon le flux BDD, ATDD et TDD obligatoire du projet:

1. vérifier l'état GREEN existant;
2. écrire ou compléter la spécification DDD du comportement;
3. formuler le scénario métier au format `Given-When-Then`;
4. ajouter le test d'acceptation automatisé RED;
5. créer le commit RED avec uniquement scénario et test;
6. ajouter les tests unitaires nécessaires;
7. implémenter strictement le domaine, les cas d'usage et les ports requis;
8. obtenir GREEN avec tests, lint et contrôles d'architecture configurés;
9. créer le commit GREEN avec uniquement l'implémentation et les ajustements requis.

Règles permanentes:

- aucune valeur par défaut implicite;
- aucun fallback silencieux;
- aucune conversion ambiguë;
- aucune gestion d'erreur générique non justifiée;
- aucune variable d'environnement acceptée comme entrée de configuration applicative;
- aucun fallback vers les variables d'environnement, fichiers `.env`, `env_file` ou valeurs `environment:` Compose;
- un seul fichier de configuration applicative chargé explicitement au démarrage de chaque processus;
- aucun accès direct au stockage possédé par un autre bounded context;
- aucune sortie de modèle probabiliste ne change seule un état métier protégé;
- aucune réponse factuelle publiée sans preuve localisable ou statut d'abstention explicite;
- aucun backtest calculé ou estimé par le LLM.

## 3. Préconditions connues

- État GREEN/RED connu: le dépôt courant ne contient pas encore de suite applicative exécutable visible dans le working tree; le milestone M-000 doit créer les commandes de test et de lint minimales.
- Présence des milestones amont dans `master`: aucun dossier `docs/tasks/milestone_NNN` n'est visible dans `master` au moment de ce plan.
- Décisions manquantes ou à matérialiser: la spécification v4.1 référence des ADR dans `docs/adr/`; leur présence effective doit être vérifiée avant toute implémentation structurante.
- Règle de planification détaillée: les fichiers de tâches `docs/tasks/milestone_NNN/*.md` doivent être créés milestone par milestone, uniquement lorsque les milestones amont requis sont présents dans `master`.

Commande de vérification avant de détailler un milestone:

```console
git fetch origin --prune
git ls-tree -r --name-only master -- docs/tasks docs/adr docs/specs
```

## 4. Workstreams

| Code | Workstream | Responsabilité | Bounded contexts ou couche | Définition de terminé |
|---|---|---|---|---|
| WS-01 | Gouvernance, ADR et traçabilité | Maintenir décisions, conformité spec-code-tests, conventions BDD/TDD et absence de dérive silencieuse | Transverse | Matrice de traçabilité maintenue, ADR à jour, critères V1 suivis |
| WS-02 | Langage publié et frontières DDD | Établir les contrats intercontextes, les identifiants, les événements et les règles de dépendance | SP, KA, EG, RA, CV, SD, EX | Contrats versionnés, tests de contrats et tests d'architecture en place |
| WS-03 | Plateforme locale et inférence | Fournir `docker-local`, configuration applicative stricte, jobs, outbox, observabilité, sécurité réseau et `llm-gateway` vers le Spark | `platform` | Services locaux non exposés, fichier de configuration unique validé, inférence Spark jointe uniquement via gateway, erreurs explicites |
| WS-04 | Traitement des sources | Enregistrer, diagnostiquer, router, convertir, contrôler et publier les versions canoniques | SP | Original immuable, page manifest complet, version canonique publiée, citation résolvable |
| WS-05 | Accès aux connaissances | Construire les projections régénérables et retourner des preuves candidates traçables | KA | Projection versionnée, recherche hybride derrière un port, `SourceLocator` résolvable |
| WS-06 | Gouvernance des preuves | Créer, vérifier, relier et versionner les claims et leurs preuves | EG | Claim sans preuve directe refusé, portée conservée, dépendances comptabilisées |
| WS-07 | Recherche et réponse | Planifier la recherche, sceller les preuves, analyser contradictions et publier des réponses vérifiées | RA | Réponse non supportée refusée, abstention fonctionnelle, citations ouvrables |
| WS-08 | Conversation et API produit | Conserver la continuité du dialogue, résoudre les références et router les demandes utilisateur | CV | Tours append-only, question résolue autonome, historique non utilisé comme preuve |
| WS-09 | Conception de stratégies | Formaliser des stratégies candidates, attribuer les règles et produire des snapshots immuables | SD | Règle sans origine bloquante, paramètres à calibrer explicités, snapshot compilable |
| WS-10 | Expérimentation | Exécuter des protocoles déterministes et conserver tous les résultats | EX | Entrées figées, résultats immuables, résultats négatifs consultables |
| WS-11 | Évaluation et exploitation | Mesurer conversion, recherche, réponses, modèles, backtests, sauvegarde et exploitation locale | Transverse | Benchmarks publiés, seuils justifiés, runbooks et acceptation V1 validés |

## 5. Vue des milestones

| Milestone | Nom | Objectif métier | Workstreams principaux | Dépendances |
|---|---|---|---|---|
| M-000 | Gouvernance exécutable | Rendre le projet pilotable par tests, ADR et traçabilité | WS-01 | Aucune |
| M-001 | Frontières DDD et contrats publiés | Stabiliser le langage commun et les contrats entre contextes | WS-01, WS-02 | M-000 |
| M-002 | Plateforme locale sûre | Exécuter commandes, jobs, outbox et inférence sans exposition publique | WS-03, WS-11 | M-001 |
| M-003 | Source enregistrée, diagnostiquée et routée | Identifier les PDF, diagnostiquer les pages et décider une route explicite | WS-04 | M-001, M-002 |
| M-004 | Version canonique publiée | Produire une version documentaire canonique contrôlée et immutable | WS-04, WS-11 | M-003 |
| M-005 | Projection de connaissance recherchable | Rechercher des passages avec provenance résolvable | WS-05, WS-11 | M-004 |
| M-006 | Claims vérifiables | Refuser les affirmations sans preuve directe et conserver portée et dépendances | WS-06 | M-004, M-005 |
| M-007 | Réponse documentaire vérifiée | Produire une réponse citée, qualifiée ou explicitement abstinente | WS-06, WS-07 | M-006 |
| M-008 | Conversation produit | Permettre une conversation suivie sans traiter l'historique comme preuve | WS-08, WS-07 | M-007 |
| M-009 | Recherche approfondie multi-sources | Couvrir, comparer et synthétiser convergences, contradictions et limites | WS-06, WS-07, WS-08 | M-008 |
| M-010 | Stratégie candidate attribuée | Transformer un résultat vérifié en stratégie compilable ou diagnostic bloquant | WS-09, WS-06, WS-07 | M-009 |
| M-011 | Expérience reproductible | Exécuter un backtest déterministe avec entrées figées et résultat conservé | WS-10, WS-09 | M-010 |
| M-012 | Évaluation pilote et calibration | Mesurer le système sur corpus pilote et justifier les seuils | WS-11, tous | M-011 |
| M-013 | Durcissement et acceptation V1 | Valider sécurité, exploitation, régression et critères V1 | WS-01, WS-03, WS-11 | M-012 |
| M13-config | Configuration applicative sans environnement | Remplacer toute entrée de processus par variables d'environnement par un fichier de configuration unique, explicite et validé | WS-01, WS-03, WS-11 | M-012; sous-milestone de M-013 |
| M13-environments | Environnements explicites et données étanches | Démarrer `development`, `test` ou `production` par une commande UV dédiée et garantir que données, secrets, files et workers restent liés au profil choisi | WS-01, WS-03, WS-11 | M-012, M13-config; sous-milestone de M-013 |
| M13-FastAPI | API orchestratrice ASGI raccordée | Remplacer le routeur HTTP artisanal par une frontière ASGI structurée et raccorder les contrats documentaires aux cas d'usage réels | WS-01, WS-03, WS-04, WS-05, WS-08, WS-11 | M-012; sous-milestone de M-013 |

## 6. Milestones détaillés

### M-000 - Gouvernance exécutable

- Source: sections 0, 3, 20, 21 et 22 de la spécification v4.1.
- Objectif métier: rendre l'implémentation contrôlable avant toute fonctionnalité, avec règles de preuve, tests et décisions visibles.
- Workstreams actifs: WS-01.
- Bounded contexts concernés: tous, sans implémentation métier encore.
- Scénario directeur:
  - Given une spécification v4.1 normative
  - When un développement est lancé
  - Then les commandes de test, lint, traçabilité et ADR existent avant le premier comportement métier
- Livrables:
  - arborescence documentaire minimale;
  - registre ADR présent et aligné avec la spécification;
  - conventions de nommage des tâches `docs/tasks/milestone_NNN`;
  - matrice initiale `exigence -> test -> code -> ADR`;
  - commandes de validation initiales;
  - définition d'achèvement transverse.
- Tests et gates:
  - smoke test de l'outillage;
  - test de présence des répertoires et fichiers de gouvernance;
  - vérification que les commandes de validation échouent explicitement si un outil requis manque.
- Sortie attendue: le projet sait dire GREEN ou RED sans ambiguïté.

### M-001 - Frontières DDD et contrats publiés

- Source: sections 2, 4, 13, 14, 15 et 21.
- Objectif métier: donner aux sept bounded contexts une frontière explicite et un langage publié stable.
- Workstreams actifs: WS-01, WS-02.
- Bounded contexts concernés: SP, KA, EG, RA, CV, SD, EX.
- Scénario directeur:
  - Given sept bounded contexts identifiés
  - When un contexte doit communiquer avec un autre
  - Then il utilise un contrat publié versionné et ne lit pas le modèle interne du producteur
- Livrables:
  - modules de contexte avec couches `domain`, `application`, `adapters`;
  - contrats `CanonicalSourceRef`, `SourceLocator`, `EvidenceRef`, `VerifiedClaimRef`, `VerifiedResearchOutcome`, `StrategySnapshot`, `ExperimentResult`;
  - enveloppe d'événement versionnée;
  - erreurs métier stables;
  - tests de contrat producteur et consommateur;
  - tests d'architecture interdisant imports et accès croisés non autorisés.
- Tests et gates:
  - sérialisation et désérialisation stable des contrats;
  - refus d'un `SourceLocator` pointant une version invalide;
  - détection automatisée des dépendances intercontextes interdites.
- Sortie attendue: l'architecture peut accueillir les comportements métier sans mélanger les modèles.

### M-002 - Plateforme locale sûre

- Source: sections 13, 15, 16, 18, 19, 20 et 21.
- Objectif métier: exécuter les traitements locaux, jobs et inférences sans exposer les données ni masquer les pannes.
- Workstreams actifs: WS-03, WS-11.
- Bounded contexts concernés: `platform`, tous par dépendance technique.
- Scénario directeur:
  - Given une demande d'inférence nécessitant Gemma
  - When `spark-inference` est indisponible ou son certificat invalide
  - Then l'état `LLM_UNAVAILABLE` ou l'erreur TLS explicite est retourné sans changer l'état métier
- Livrables:
  - configuration locale `docker-local`;
  - fichier `config/application.yaml` chargé explicitement par chaque processus applicatif;
  - validateur bloquant les variables d'environnement applicatives et tout fallback de configuration;
  - services PostgreSQL, Qdrant, API, workers, `llm-gateway`, observabilité;
  - aucune présence de Gemma ou vLLM principal dans le Compose local;
  - outbox transactionnelle et consommateurs idempotents;
  - file de jobs avec priorités et idempotence;
  - contract test compatible OpenAI entre `llm-gateway` et vLLM Spark;
  - règles réseau limitant l'accès Spark au seul gateway.
- Tests et gates:
  - aucun port PostgreSQL, Qdrant, worker ou Spark exposé publiquement;
  - retry autorisé uniquement avant premier token;
  - sortie partielle non publiée;
  - duplication d'événement sans double transition métier;
  - logs sans corps complets de prompts et réponses.
- Sortie attendue: les futures capacités métier disposent d'une exécution locale sûre et auditable.

### M-003 - Source enregistrée, diagnostiquée et routée

- Source: sections 5, 12, 17, 19, 20 et 21.
- Objectif métier: enregistrer un document source immuable, diagnostiquer chaque page et produire une route explicite sans bascule silencieuse.
- Workstreams actifs: WS-04.
- Bounded context propriétaire: SP.
- Scénario directeur:
  - Given un PDF original ajouté au corpus
  - When le diagnostic et le routage sont demandés
  - Then chaque page reçoit un état, une route et une justification, ou le document passe en revue explicite
- Livrables:
  - agrégats `SourceDocument` et `DocumentProcessingRun`;
  - inventaire par hash stable;
  - page manifest complet;
  - diagnostic page par page;
  - politique de routage;
  - états `ROUTE_PLANNED`, `MANUAL_REVIEW`, `QUARANTINED`;
  - endpoints `POST /v1/documents` et `POST /v1/documents/{id}/diagnose`.
- Tests et gates:
  - aucun original modifié;
  - 100 % des pages présentes dans le manifest;
  - route incertaine refusée au lieu d'être remplacée implicitement;
  - document en quarantaine non publiable.
- Sortie attendue: le système sait décider explicitement comment traiter une source.

### M-004 - Version canonique publiée

- Source: sections 5, 12, 14, 17, 19, 20 et 21.
- Objectif métier: produire une version canonique structurée, contrôlée, immutable et publiable vers les contextes aval.
- Workstreams actifs: WS-04, WS-11.
- Bounded context propriétaire: SP.
- Scénario directeur:
  - Given une page avec une sortie native et une sortie Granite
  - When l'adjudication est terminée
  - Then une seule autorité textuelle est retenue, les autres sorties restent auditées et la justification est enregistrée
- Livrables:
  - agrégat `CanonicalSource`;
  - adaptateurs Docling, Granite-Docling et OCRmyPDF conditionnel;
  - fusion pagewise;
  - contrôle qualité pré et post-conversion;
  - JSON Docling canonique;
  - exports régénérables;
  - événement `CanonicalSourcePublished`;
  - endpoint `POST /v1/documents/{id}/convert`.
- Tests et gates:
  - version en quarantaine non publiable;
  - correction créant une nouvelle version sans modifier l'ancienne;
  - aucune page omise;
  - `SourceLocator` résolvable jusqu'à page et item;
  - QA refusant chiffres, signes ou tableaux incohérents selon politique.
- Sortie attendue: les contextes aval peuvent consommer une source canonique fiable.

### M-005 - Projection de connaissance recherchable

- Source: sections 6, 12, 14, 17, 19, 20 et 21.
- Objectif métier: rendre les versions canoniques interrogeables sans confondre projection et source de vérité.
- Workstreams actifs: WS-05, WS-11.
- Bounded context propriétaire: KA.
- Scénario directeur:
  - Given une projection `SEARCHABLE`
  - When la recherche retourne un passage
  - Then le passage contient un `SourceLocator` résolvable et un `content_hash` cohérent
- Livrables:
  - agrégat `KnowledgeProjection`;
  - chunking hiérarchique;
  - enrichissement de métadonnées;
  - embeddings et recherche sparse;
  - collection Qdrant régénérable;
  - fusion hybride et reranking derrière un port;
  - endpoint `POST /v1/search`;
  - métriques Recall@k, MRR, nDCG initiales.
- Tests et gates:
  - source en quarantaine non indexable;
  - projection reconstruisible;
  - filtres de métadonnées vérifiés;
  - absence d'accès direct de RA à Qdrant;
  - recherche renvoyant scores, citations et provenance.
- Sortie attendue: RA et EG peuvent demander des preuves candidates sans dépendre de Qdrant.

### M-006 - Claims vérifiables

- Source: sections 7, 12, 14, 16, 17, 19, 20 et 21.
- Objectif métier: protéger le passage d'une formulation plausible à une affirmation vérifiée.
- Workstreams actifs: WS-06.
- Bounded context propriétaire: EG.
- Scénario directeur:
  - Given une affirmation à l'état `UNDER_VERIFICATION`
  - When aucune preuve admissible `SUPPORTS_DIRECTLY` n'existe
  - Then l'affirmation ne passe pas à `VERIFIED` et la raison est enregistrée
- Livrables:
  - agrégats `Claim`, `VerificationCase`, `DependencyGroup`;
  - extraction atomique structurée;
  - politique d'admissibilité;
  - conservation de la portée;
  - groupes de dépendance;
  - relations support, contradiction, généralisation et dépendance;
  - endpoints `POST /v1/claims/extract`, `POST /v1/claims/{id}/verify`, `GET /v1/claims/{id}/evidence`.
- Tests et gates:
  - condition de preuve jamais élargie silencieusement;
  - trois reprises d'une même étude comptées comme une seule confirmation indépendante;
  - sortie LLM traduite en proposition puis décidée par politique;
  - claim rejeté ou supersédé conservé.
- Sortie attendue: le registre de preuves devient le coeur vérifiable du système.

### M-007 - Réponse documentaire vérifiée

- Source: sections 8, 12, 16, 17, 19, 20 et 21.
- Objectif métier: produire une réponse utile dont les assertions importantes sont supportées, qualifiées ou retirées.
- Workstreams actifs: WS-06, WS-07.
- Bounded context propriétaire: RA.
- Scénario directeur:
  - Given un brouillon contenant une assertion factuelle importante
  - When aucune preuve admissible ne la soutient
  - Then l'assertion est supprimée ou reformulée comme incertaine et la réponse ne devient pas `SUPPORTED`
- Livrables:
  - agrégats `ResearchCase` et `Answer`;
  - `ResearchMandate`;
  - recherche locale simple;
  - jeu de preuves scellé;
  - assemblage de preuves;
  - vérification des assertions de réponse;
  - statuts `SUPPORTED`, `PARTIALLY_SUPPORTED`, `INSUFFICIENT_EVIDENCE`, `CONFLICTING_EVIDENCE`, `REQUIRES_CURRENT_DATA`;
  - endpoint `POST /v1/answer`.
- Tests et gates:
  - abstention si données actuelles requises mais non autorisées;
  - contradiction conditionnelle classée sans généralisation abusive;
  - citation ouvrable pour chaque assertion factuelle conservée;
  - aucune valeur de marché inventée.
- Sortie attendue: le système peut répondre sans présenter une hypothèse comme connaissance.

### M-008 - Conversation produit

- Source: sections 9, 12, 17, 18, 19, 20 et 21.
- Objectif métier: permettre une interaction suivie tout en séparant mémoire conversationnelle et preuve factuelle.
- Workstreams actifs: WS-08, WS-07.
- Bounded context propriétaire: CV.
- Scénario directeur:
  - Given une conversation portant sur le volatility targeting
  - When l'utilisateur écrit `compare-la maintenant à Kelly`
  - Then une question autonome mentionnant explicitement les deux méthodes est produite
- Livrables:
  - agrégats `Conversation` et `ConversationTurn`;
  - `ConversationContextSnapshot`;
  - routage de mode documentaire, approfondi, stratégie, calcul ou backtest;
  - endpoints de conversation et endpoint compatible `/v1/chat/completions`;
  - API de consultation de tours;
  - rattachement des réponses vérifiées aux tours;
  - affichage produit minimal des citations et statuts.
- Tests et gates:
  - historique non utilisé comme preuve autonome;
  - assertion réutilisée recherchée et vérifiée à nouveau;
  - suppression ou archivage de conversation sans suppression cascade des connaissances;
  - mode choisi visible et justifié.
- Sortie attendue: le produit devient un chatbot local utile sans rompre la chaîne de preuve.

### M-009 - Recherche approfondie multi-sources

- Source: sections 7, 8, 12, 17, 19, 20 et 21.
- Objectif métier: analyser convergences, contradictions, limites, dépendances et lacunes sur plusieurs sources.
- Workstreams actifs: WS-06, WS-07, WS-08.
- Bounded context propriétaire: RA, avec EG comme fournisseur de claims vérifiés.
- Scénario directeur:
  - Given deux affirmations opposées portant sur des horizons différents
  - When l'analyse des contradictions est exécutée
  - Then la relation est classée `DIFFERENT_HORIZON` et la réponse explique la condition
- Livrables:
  - planificateur de recherche approfondie;
  - obligations de couverture;
  - recherches multi-requêtes;
  - analyse de contradictions et compatibilités;
  - synthèse multi-sources;
  - endpoint `POST /v1/research/deep`;
  - métriques de couverture documentaire.
- Tests et gates:
  - limites et conditions conservées dans la synthèse;
  - contradictions non résolues visibles;
  - couverture insuffisante produisant un statut explicite;
  - distinction source, déduction et choix de conception.
- Sortie attendue: le système peut produire une analyse approfondie sans effacer les nuances des études.

### M-010 - Stratégie candidate attribuée

- Source: sections 10, 12, 17, 18, 19, 20 et 21.
- Objectif métier: transformer un résultat vérifié en stratégie candidate déterministe, attribuée et compilable ou en diagnostic bloquant.
- Workstreams actifs: WS-09, WS-06, WS-07.
- Bounded context propriétaire: SD.
- Scénario directeur:
  - Given une stratégie candidate comportant une règle d'entrée sans `RuleOrigin`
  - When la validation de compilation est demandée
  - Then la stratégie passe à `INCOMPLETE` et la règle devient un diagnostic bloquant
- Livrables:
  - agrégat `StrategyCandidate`;
  - entités `StrategyRule` et `StrategyParameter`;
  - origines `SOURCE`, `DEDUCTION`, `DESIGN_CHOICE`, `PARAMETER_TO_CALIBRATE`, `USER_CONSTRAINT`;
  - `StrategyCompiler`;
  - analyse de compatibilité;
  - snapshot immuable `StrategySnapshot`;
  - endpoints `POST /v1/strategies/compile` et `GET /v1/strategies/{id}`.
- Tests et gates:
  - paramètre à calibrer refusé sans domaine ni protocole;
  - règle documentaire conservant `ClaimId`, version et `EvidenceRefs`;
  - mandat utilisateur appliqué;
  - stratégie compilable sans paramètre bloquant non résolu.
- Sortie attendue: une stratégie n'est jamais un texte séduisant, mais une hypothèse attribuée et vérifiable.

### M-011 - Expérience reproductible

- Source: sections 11, 12, 14, 17, 19, 20 et 21.
- Objectif métier: exécuter une stratégie snapshotée avec entrées figées et conserver tous les résultats.
- Workstreams actifs: WS-10, WS-09.
- Bounded context propriétaire: EX.
- Scénario directeur:
  - Given une expérience `RUNNING`
  - When la modification du modèle de coûts est demandée
  - Then la commande est refusée et une nouvelle expérience doit être planifiée
- Livrables:
  - agrégat `Experiment`;
  - `ExperimentResult`;
  - snapshot de données;
  - modèle de coûts figé;
  - adaptateur `DeterministicBacktestEngineAdapter`;
  - registre append-only des expériences;
  - endpoints `POST /v1/strategies/{id}/backtest` et `GET /v1/experiments/{id}`.
- Tests et gates:
  - résultat négatif conservé et consultable;
  - métriques provenant du moteur de backtest, jamais du LLM;
  - reproduction depuis `spec_hash`, `data_snapshot`, paramètres, modèle de coûts et version de code;
  - résultats échoués enregistrés avec cause explicite.
- Sortie attendue: les hypothèses de stratégie deviennent expérimentables et auditables.

### M-012 - Évaluation pilote et calibration

- Source: sections 19, 20, 21 et 22.
- Objectif métier: mesurer la qualité du système sur un corpus représentatif avant acceptation.
- Workstreams actifs: WS-11, tous les workstreams métier.
- Bounded contexts concernés: tous.
- Scénario directeur:
  - Given un corpus pilote annoté
  - When les routes documentaires, la recherche, les réponses et les modèles sont évalués
  - Then les seuils et promotions sont justifiés par métriques et non par préférence implicite
- Livrables:
  - corpus pilote de 50 à 100 PDF;
  - jeu annoté page par page;
  - benchmark de routes documentaires;
  - benchmark des modèles Gemma candidats via le chemin réel `docker-local -> llm-gateway -> Spark`;
  - benchmark recherche sur 100 à 300 questions;
  - benchmark réponses;
  - benchmark backtests;
  - seuils calibrés;
  - rapport des écarts V1.
- Tests et gates:
  - CER/WER, exactitude numérique, signes, tableaux et ordre de lecture mesurés;
  - Recall@5, Recall@10, Recall@20, MRR et nDCG publiés;
  - précision des citations et taux d'abstention mesurés;
  - aucun checkpoint communautaire promu sans benchmark supérieur ou égal aux références;
  - un test scientifique échoué ne peut pas être masqué par un test logiciel GREEN.
- Sortie attendue: les décisions de promotion reposent sur des preuves mesurées.

### M-013 - Durcissement et acceptation V1

- Source: sections 18, 19, 20, 21, 22, 23 et 24.
- Objectif métier: transformer le système complet en version personnelle exploitable, sûre et maintenable.
- Workstreams actifs: WS-01, WS-03, WS-11.
- Bounded contexts concernés: tous.
- Scénario directeur:
  - Given le système complet déployé localement
  - When la gate V1 est exécutée
  - Then chaque critère d'acceptation DDD, fonctionnel, technique et sécurité est validé ou explicitement marqué non satisfait
- Livrables:
  - suite de régression complète;
  - audit réseau et sécurité;
  - sauvegardes chiffrées et test de restauration;
  - runbooks d'exploitation locale;
  - monitoring local;
  - documentation utilisateur;
  - rapport d'acceptation V1;
  - liste des écarts non acceptés.
- Tests et gates:
  - aucun service exposé publiquement;
  - Spark accessible uniquement depuis `llm-gateway`;
  - navigateur incapable d'appeler le Spark;
  - pannes Spark explicites sans corruption d'état;
  - restauration de sauvegarde testée;
  - anti-patterns interdits vérifiés par tests ou revue documentée.
- Sortie attendue: la V1 est acceptable, exploitable et conforme à la spécification.

### M13-config - Configuration applicative sans environnement

- Source: sections 0, 3, 13, 16, 18, 20, 22 et ADR-016.
- Objectif métier: rendre le lancement local reproductible et auditable sans qu'une variable d'environnement puisse piloter silencieusement l'application.
- Workstreams actifs: WS-01, WS-03, WS-11.
- Bounded contexts concernés: `platform`, `llm-gateway`, API, workers et tous les adaptateurs qui consomment une configuration.
- Dossier de tâches attendu si le jalon est détaillé: `docs/tasks/milestone_013-config`.
- Règle de gouvernance: `M13-config` est un sous-milestone de `M-013`; sa planification ne requiert pas la clôture de `M-013` dans `master`, seulement les milestones strictement antérieurs.
- Scénario directeur:
  - Given un processus applicatif reçoit un chemin `--config` vers `config/application.yaml`
  - When le processus démarre avec des variables d'environnement homonymes ou avec une clé obligatoire absente du fichier
  - Then le démarrage échoue avec une erreur de configuration explicite et aucune valeur issue de l'environnement n'est utilisée
- Livrables:
  - schéma strict de `config/application.yaml`;
  - chargeur de configuration unique pour API, workers, `llm-gateway` et scripts de déploiement Spark;
  - suppression des entrées `environment:`, `env_file`, `.env` et variables système applicatives des chemins de lancement;
  - mapping documenté des anciennes clés `GEMMA_*`, `DATABASE_URL`, `QDRANT_URL`, `LLM_GATEWAY_URL` et ports vers les sections du fichier;
  - erreurs publiques de configuration `CONFIG_FILE_REQUIRED`, `CONFIG_SCHEMA_INVALID`, `CONFIG_KEY_MISSING`, `CONFIG_KEY_EMPTY` et `CONFIG_ENV_INPUT_REJECTED`;
  - runbook de démarrage local par fichier de configuration;
  - rapport d'audit prouvant l'absence de fallback vers l'environnement.
- Tests et gates:
  - démarrage sans `--config` refusé;
  - fichier absent ou invalide refusé;
  - clé obligatoire absente ou vide refusée;
  - variable d'environnement applicative homonyme refusée, même si le fichier est valide;
  - Compose local sans `environment:` ni `env_file` pour les valeurs applicatives;
  - recherche statique bloquant `os.environ`, `getenv`, `process.env` ou équivalent dans le code applicatif hors adaptateur de validation qui les refuse explicitement.
- Sortie attendue: aucun processus applicatif n'accepte de variable d'environnement comme entrée; seules les valeurs présentes dans le fichier de configuration pilotent l'application.

### M13-environments - Environnements explicites et données étanches

- Source: demande utilisateur du 2026-07-21; ADR-016 à remplacer explicitement; livrables M13-config.
- Objectif métier: permettre à l'exploitant de choisir sans ambiguïté `development`, `test` ou `production` par `uv run development`, `uv run test` ou `uv run production`, tout en rendant techniquement impossible l'accès croisé aux données et travaux asynchrones.
- Workstreams actifs: WS-01, WS-03, WS-11.
- Bounded contexts concernés: `platform.configuration`, API, UI, workers, jobs/outbox, PostgreSQL, Qdrant, stockage de fichiers, secrets, exploitation et gouvernance.
- Dossier de tâches attendu si le jalon est détaillé: `docs/tasks/milestone_013-environments`.
- Règle de gouvernance: `M13-environments` est un sous-milestone de `M-013`; sa planification ne requiert pas la clôture de `M-013` dans `master`, seulement les milestones strictement antérieurs. M13-config est une dépendance fonctionnelle déjà livrée.
- Scénario directeur:
  - Given les trois configurations complètes `development`, `test` et `production` et leurs ressources mutables distinctes
  - When l'exploitant lance l'une des trois commandes UV et soumet un PDF au parcours public réel
  - Then l'API, l'outbox, le relais, les workers, PostgreSQL, Qdrant et les fichiers utilisent exclusivement l'environnement choisi, publient la progression réelle et refusent toute incohérence d'identité avant le premier travail
- Livrables:
  - ADR-046 remplaçant ADR-045, décidant les profils locaux explicites sur une autorité Docker honnêtement déclarée et retirant le point d'entrée `ui`, sans réintroduire de variable d'environnement ni de fallback;
  - contrat strict `environment` et `deployment_id`, avec trois fichiers complets `config/environments/development.yaml`, `test.yaml` et `production.yaml` sans héritage implicite;
  - scripts UV `development`, `test` et `production` comme seules commandes opérateur, avec mapping interne non configurable vers le fichier attendu;
  - stockages, rôles, credentials, volumes, réseaux, chemins, artefacts, caches, files et outbox distincts par environnement;
  - contrôle d'identité des stockages avant toute lecture, écriture, migration ou prise de job;
  - identité d'environnement propagée aux jobs, workers, états de santé, progressions et preuves d'exécution;
  - opérations de migration, sauvegarde, restauration, purge et nettoyage bornées à l'environnement explicitement sélectionné;
  - parcours réel `PDF -> API -> persistance -> outbox -> relais -> worker -> projection -> lecture publique` prouvé séparément dans les trois environnements;
  - runbooks, matrice de traçabilité et gate M13-environments rejouable.
- Tests et gates:
  - profil absent, inconnu, incomplet ou contradictoire refusé sans valeur par défaut;
  - `uv run development`, `uv run test` et `uv run production` sélectionnent chacun un unique fichier et supervisent toute la chaîne attendue;
  - aucune URL mutable, base, rôle, secret, volume, racine de fichiers, file ou outbox n'est partagé entre deux profils;
  - un stockage portant une identité différente produit `DATASTORE_ENVIRONMENT_MISMATCH` avant toute opération métier;
  - un worker ne réclame que les jobs de son environnement et refuse explicitement un message divergent avec `WORKER_ENVIRONMENT_MISMATCH`;
  - l'UI n'active une action asynchrone que si sa chaîne réelle est prête et lit la progression exclusivement depuis le contrat public du profil courant;
  - le nettoyage de `test` est impossible sur `development` ou `production`;
  - chaque parcours bout en bout utilise un PDF réel, les adaptateurs réels et les stockages réels, sans mock, stub, fake ni fallback;
  - `uv run --locked gate` reste GREEN après enrôlement des validations.
- Sortie attendue: les trois commandes simples pilotent des installations complètes, observables et étanches; aucune donnée ni aucun worker d'un environnement n'est accessible depuis les deux autres.

### M13-FastAPI - API orchestratrice ASGI raccordée

- Source: ADR-018, spécifications M-003 à M-005, `docs/specs/ui.md` et demande utilisateur du 2026-07-12.
- Objectif métier: fournir une frontière HTTP publique explicite, testable et maintenable qui préserve les contrats existants et délègue les commandes et lectures documentaires aux bounded contexts propriétaires.
- Workstreams actifs: WS-01, WS-03, WS-04, WS-05, WS-08, WS-11.
- Bounded contexts concernés: `platform` pour la composition HTTP, SP pour les sources, diagnostics et conversions, KA pour les projections, et UI comme client exclusif de l'API orchestratrice.
- Dossier de tâches attendu si le jalon est détaillé: `docs/tasks/milestone_013-fastapi`.
- Règle de gouvernance: `M13-FastAPI` est un sous-milestone de `M-013`; sa planification ne requiert pas la clôture de `M-013` dans `master`, seulement les milestones strictement antérieurs.
- Scénario directeur:
  - Given un client appelle un contrat public existant ou documentaire de l'API orchestratrice
  - When la requête est servie par l'application ASGI locale
  - Then le contrat HTTP délègue au cas d'usage propriétaire, conserve les erreurs publiques et ne déclenche aucun mock, stub, fake ni fallback
- Livrables:
  - ADR décidant `FastAPI + Uvicorn` pour `orchestrator-api` sans imposer ce framework aux bounded contexts;
  - application ASGI construite par une factory et composition root explicite au démarrage;
  - migration sans régression des routes existantes de santé, conversation, évaluation, recherche et indexation;
  - routeur documentaire pour l'enregistrement PDF et le lancement du diagnostic;
  - read-models publics SP pour le corpus, le diagnostic et la conversion;
  - read-model public KA pour la projection;
  - récupération contrôlée du PDF original sans exposition de référence de stockage;
  - UI consommant exclusivement les contrats de l'API orchestratrice;
  - lancement Uvicorn, healthchecks Compose, OpenAPI borné, observabilité et gates de non-régression.
- Tests et gates:
  - parité exacte des statuts, corps et codes d'erreur des routes publiques préexistantes;
  - upload PDF `multipart/form-data` strict, sans métadonnée inventée ni lecture complète non bornée implicite;
  - preuve `HTTP -> routeur -> cas d'usage -> port -> adaptateur réel` pour les commandes documentaires;
  - lectures diagnostic, conversion et projection sans reconstruction depuis les logs ou les stockages techniques;
  - PDF original restitué bit à bit avec `application/pdf`, sans `original_storage_ref` public;
  - UI incapable d'appeler directement un repository, un chemin métier, Qdrant, PostgreSQL, un worker ou Spark;
  - dépendance indisponible rendue par une erreur publique explicite, sans backend alternatif;
  - test HTTP réel et test OpenAPI sur l'application ASGI.
- Sortie attendue: `orchestrator-api` est une façade HTTP ASGI mince et opérationnelle; l'UI observe et déclenche le pipeline documentaire uniquement par ses contrats publics raccordés.

## 7. Chemin critique

Chemin critique pour obtenir un chatbot documentaire cité:

```text
M-000 -> M-001 -> M-002 -> M-003 -> M-004 -> M-005 -> M-006 -> M-007 -> M-008
```

Chemin critique pour la V1 complète:

```text
M-008 -> M-009 -> M-010 -> M-011 -> M-012 -> M-013
M-012 -> M13-config
M-012 -> M13-config -> M13-environments
M-012 -> M13-FastAPI
```

La plateforme M-002 peut avancer en parallèle des premières spécifications détaillées de M-003 uniquement si M-001 est accepté et présent dans `master`.

## 8. Gates transverses par milestone

Chaque milestone doit produire:

- au moins un scénario `Given-When-Then` métier;
- au moins un test d'acceptation RED avant implémentation;
- les tests unitaires des invariants touchés;
- les tests de contrat si un langage publié est créé ou modifié;
- les tests d'architecture si une frontière DDD est touchée;
- les tests de processus si un workflow intercontexte est introduit;
- les métriques ou logs nécessaires à l'audit du comportement;
- un commit RED puis un commit GREEN;
- une entrée dans la matrice de traçabilité.

## 9. Jalons de décision ADR

Les points suivants doivent déclencher une vérification ADR avant implémentation:

| Décision | Moment minimal | ADR attendue si non matérialisée |
|---|---|---|
| Artefacts canoniques PDF et Docling JSON | M-004 | Oui |
| Routage hybride Docling, Granite et OCRmyPDF conditionnel | M-003 ou M-004 | Oui |
| Autorité textuelle unique par page | M-004 | Oui |
| Recherche hybride et Qdrant comme projection | M-005 | Oui |
| Registre de claims séparé de l'index documentaire | M-006 | Oui |
| Monolithe modulaire et cycles de vie séparés | M-001 | Oui |
| Cohérence éventuelle intercontextes par outbox | M-002 | Oui |
| Topologie `docker-local` et `spark-inference` | M-002 | Oui |
| Gemma 4 servi par vLLM sur Spark | M-002 | Oui |
| Snapshots immuables pour stratégies et expériences | M-010 ou M-011 | Oui |
| Configuration applicative par fichier unique sans variables d'environnement | M13-config | ADR-016 |
| Profils `development`, `test`, `production` explicites et isolation des données/workers | M13-environments | ADR-046, remplaçant ADR-045 qui remplaçait ADR-016 |
| Framework ASGI et serveur HTTP de l'API orchestratrice | M13-FastAPI | ADR-019 à créer |

Une ADR acceptée ne doit pas être réécrite pour changer son sens. Toute évolution doit créer une nouvelle ADR remplaçante.

## 10. Règles de création des tâches détaillées

Avant d'implémenter un milestone `M-NNN`:

1. vérifier que tous ses milestones amont sont visibles dans `master`;
2. créer `docs/tasks/milestone_NNN`;
3. créer un fichier par tâche verticale au format `NNNN_slug.md`;
4. commencer par `0001_verifier_precondition_green.md`;
5. écrire les tâches dans le langage métier du bounded context;
6. inclure pour chaque tâche le scénario BDD, le test d'acceptation RED, les tests unitaires, l'implémentation attendue, les invariants, les dépendances, les commandes de validation, le commit RED et le commit GREEN.

Si un milestone amont requis n'est pas présent dans `master`, la création du dossier de tâches du milestone aval doit être refusée.

## 11. Risques structurants et contrôles

| Risque | Contrôle prévu |
|---|---|
| Conversion documentaire fidèle en apparence mais fausse sur chiffres ou tableaux | QA M-004 et évaluation pilote M-012 |
| Citations non ouvrables | `SourceLocator` M-001, SP M-004, KA M-005, gate RA M-007 |
| Confusion entre projection Qdrant et source de vérité | Contrats M-001, KA M-005, tests d'architecture |
| Réponse plausible sans preuve | EG M-006, RA M-007, statuts d'abstention |
| Historique conversationnel traité comme source | CV M-008 et test dédié |
| Paramètres de stratégie inventés | SD M-010, origine obligatoire et protocole de calibration |
| Backtest non reproductible | EX M-011, entrées figées et registre append-only |
| Résultat négatif effacé | EX M-011, rétention M-013 |
| Spark ou vLLM exposé directement | Plateforme M-002 et audit M-013 |
| Panne Spark masquée | Gateway M-002, tests de processus et absence de fallback silencieux |
| Critère scientifique ignoré après GREEN logiciel | Évaluation M-012 séparant tests logiciels et métriques scientifiques |
| Configuration pilotée par variable d'environnement ou valeur système | M13-config, chargeur strict, audit Compose et scan statique |
| Donnée ou job consommé depuis un autre environnement | M13-environments, ressources distinctes, identité de stockage et refus worker avant claim |

## 12. Livrable V1 attendu

À la fin de M-013 et de ses sous-milestones applicables, l'utilisateur doit pouvoir:

- charger un corpus personnel de PDF;
- obtenir des versions canoniques contrôlées et traçables;
- rechercher des passages avec citations ouvrables;
- poser des questions en français ou en anglais dans une conversation locale;
- recevoir une réponse vérifiée, qualifiée ou abstinente;
- lancer une recherche approfondie multi-sources;
- consulter claims, preuves, contradictions et limites;
- compiler une stratégie candidate dont chaque règle possède une origine;
- exécuter une expérience reproductible par code déterministe;
- conserver les résultats positifs, négatifs et échoués;
- auditer les décisions, modèles, versions, données et configurations;
- démarrer la pile complète avec `uv run development`, `uv run test` ou `uv run production`, chaque commande utilisant exclusivement sa configuration et ses données;
- exploiter le système localement sans exposition publique.
