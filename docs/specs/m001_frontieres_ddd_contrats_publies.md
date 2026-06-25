# M-001 - Frontières DDD et contrats publiés

## Statut

- Milestone: M-001 - Frontières DDD et contrats publiés.
- Source canonique: `docs/specs/plan_implementation_milestones_workstreams.md`, section `M-001 - Frontières DDD et contrats publiés`.
- Spécification normative: `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 2, 4, 13, 14, 15 et 21.
- ADR consultées: DDD-ADR-001, DDD-ADR-002, DDD-ADR-003.

Cette spécification matérialise la carte DDD v4.1 pour M-001. Elle ne crée pas de nouveau bounded context, ne crée pas de persistance concrète et ne publie aucun modèle interne comme contrat intercontexte.

## Scénario BDD

- Given les sept bounded contexts sont définis dans la spécification v4.1.
- When la spécification M-001 est publiée.
- Then chaque communication intercontexte nomme son contrat publié, son producteur, son consommateur et le modèle interne qui reste interdit.

## Contexte DDD

- Domaine: langage publié et conception de frontières intercontextes.
- Bounded context: transverse pour SP, KA, EG, RA, CV, SD et EX.
- Objectif métier: donner aux sept bounded contexts une frontière explicite et un langage publié stable avant les contrats détaillés et les modules.
- Décision structurante: les contextes restent des frontières de modèle dans un monolithe modulaire, avec cycles de vie séparés et contrats versionnés.

## Langage ubiquitaire M-001

| Terme | Sens M-001 |
|---|---|
| bounded context | frontière dans laquelle un modèle, ses invariants et son langage ont un sens précis |
| responsabilité exclusive | mission possédée par un seul contexte, non partagée par convention implicite |
| langage publié | vocabulaire et structure contractuelle acceptés pour une communication intercontexte |
| propriétaire de données | contexte responsable de l'état métier logique, des artefacts et des transitions associées |
| contrat versionné | représentation publiée compatible en lecture et indépendante d'un framework ou d'une persistance |
| façade applicative | point d'entrée application qui coordonne une demande sans posséder le modèle du contexte appelé |
| anti-corruption layer | traduction explicite entre deux langages de contexte pour éviter la propagation d'un modèle interne |

## Contextes propriétaires

| Code | Bounded context | Responsabilité exclusive | Propriétaire de données | Modèle interne interdit |
|---|---|---|---|---|
| SP | Traitement des sources | enregistrer, diagnostiquer, convertir, contrôler et publier les versions documentaires canoniques | source_processing | agrégats, tables, fichiers de travail, diagnostics et artefacts internes SP |
| KA | Accès aux connaissances | construire les projections de recherche et retourner des preuves candidates traçables | knowledge_access | collections Qdrant, cache d'embeddings, scores et algorithmes de fusion internes |
| EG | Gouvernance des preuves | créer, vérifier, relier et versionner les affirmations et leurs preuves | evidence_governance | graphe de claims, cas de vérification et artefacts de revue internes |
| RA | Recherche et réponse | planifier une recherche, assembler les preuves, analyser les contradictions et produire une réponse vérifiée | research_answering | jeux de preuves, brouillons de réponse, rapports et états de recherche internes |
| CV | Conversation | conserver la continuité du dialogue et résoudre les références de suivi | conversation | tours, préférences et snapshots de contexte internes |
| SD | Conception de stratégies | formaliser et compiler des stratégies candidates attribuées | strategy_design | stratégie candidate mutable, règles internes et diagnostics de compilation |
| EX | Expérimentation | exécuter des protocoles reproductibles et conserver tous les résultats | experimentation | registre d'expérience, données d'exécution, diagnostics et rapports internes |

## Relations intercontextes publiées

| Relation | Producteur | Consommateur | Contrat publié | Statut M-001 | Type | Modèle interne interdit |
|---|---|---|---|---|---|---|
| SP -> KA | SP | KA | CanonicalSourcePublished | Livré | Published Language | tables, agrégats, diagnostics et chemins internes SP |
| SP -> EG | SP | EG | CanonicalSourcePublished | Livré | Published Language | tables, agrégats, diagnostics et chemins internes SP |
| KA -> RA | KA | RA | SearchEvidence API | Réservé | Customer/Supplier | Qdrant, embeddings, scores bruts et logique de fusion KA |
| EG -> RA | EG | RA | VerifiedClaimRef | Livré | Published Language | graphe de claims, cas de vérification et états internes EG |
| EG -> SD | EG | SD | VerifiedClaimRef | Livré | Published Language | graphe de claims, cas de vérification et états internes EG |
| RA -> SD | RA | SD | VerifiedResearchOutcome | Livré | Anti-Corruption Layer | brouillons de réponse, jeux de preuves et états de recherche RA |
| SD -> EX | SD | EX | StrategySnapshot | Livré | Published Language immuable | stratégie candidate mutable, paramètres ouverts et règles internes SD |
| CV -> RA | CV | RA | ResolvedQuestion | Réservé | façade applicative | historique conversationnel, tours et snapshots internes CV |
| CV -> SD | CV | SD | StrategyRequest | Réservé | façade applicative | historique conversationnel, préférences et tours internes CV |
| CV -> EX | EX | CV | GetExperiment | Réservé | façade applicative | registre d'expérience, diagnostics et artefacts internes EX |

La relation `CV -> EX` décrit la demande applicative portée par CV pour consulter un résultat ou un artefact d'expérience. EX reste producteur du contrat publié et CV reste consommateur; CV ne lit jamais le registre interne d'EX.

## Contrats attendus M-001

| Contrat publié | Producteur propriétaire | Consommateurs M-001 | Contenu minimal autorisé |
|---|---|---|---|
| CanonicalSourcePublished | SP | KA, EG | identifiants de version canonique, empreintes, politique de qualité et horodatage de publication |
| SearchEvidence API | KA | RA | requête de recherche, critères de recherche, références de preuve candidates et `SourceLocator` résolvable |
| VerifiedClaimRef | EG | RA, SD | identifiant d'affirmation, version, texte canonique, portée, statut, références de preuve et dépendances |
| VerifiedResearchOutcome | RA | SD | cas de recherche, question, mandat, statut de support, claims retenus, conflits et lacunes |
| StrategySnapshot | SD | EX | version immuable de stratégie, règles attribuées, paramètres, contraintes, exigences de données et plan de validation |
| ResolvedQuestion | CV | RA | question autonome, mandat et références utilisateur explicitement résolues |
| StrategyRequest | CV | SD | intention de conception, contraintes utilisateur et références vérifiées disponibles |
| GetExperiment | EX | CV | requête de consultation d'expérience et réponse contrôlée par EX sans exposition du registre interne |

Les lignes `Livré` correspondent aux contrats versionnés et fixtures publiés par M-001. Les lignes `Réservé` nomment la relation attendue par la context map v4.1, mais leur schéma détaillé reste à publier par un milestone ultérieur ou par une nouvelle ADR si leur sens change.

## Règles de dépendance

1. Un contexte ne lit pas le modèle interne d'un autre contexte.
2. Un contrat expose le minimum nécessaire à la communication intercontexte.
3. Un producteur est responsable de la stabilité en lecture du contrat publié.
4. Un consommateur traduit le contrat reçu dans son propre langage avant de modifier son état métier.
5. Les relations non listées dans `Relations intercontextes publiées` sont interdites pour M-001.
6. Une façade applicative ne devient pas propriétaire des preuves, stratégies ou expériences qu'elle coordonne.
7. L'anti-corruption layer RA vers SD traduit une conclusion de recherche en origine, contrainte, paramètre ou lacune; il ne convertit pas directement une réponse en règle de stratégie.
8. Les adaptateurs de plateforme, services externes, connecteurs, modèles, bases et projections ne définissent aucune frontière métier.

## Invariants M-001

- Chaque bounded context possède une responsabilité exclusive et un propriétaire de données explicite.
- Chaque communication intercontexte possède un contrat publié nommé, un producteur, un consommateur et un modèle interne interdit.
- Aucun contrat publié ne cite une table, une classe, un agrégat interne, une collection technique ou un identifiant de projection comme interface métier.
- Les cycles de vie restent locaux aux contextes propriétaires; aucune machine d'états globale ne remplace les états métier locaux.
- `SourceLocator` reste le langage publié de traçabilité documentaire entre SP, KA, EG, RA et CV.
- `StrategySnapshot` reste immuable pour EX; EX ne lit jamais une stratégie candidate mutable.
- Un résultat d'expérience reste possédé par EX même lorsqu'il est présenté ou interprété par CV ou RA.

## Critères d'acceptation M-001

- Les sept bounded contexts SP, KA, EG, RA, CV, SD et EX sont listés avec responsabilité exclusive, propriétaire de données et modèle interne interdit.
- Les relations SP vers KA et EG, KA vers RA, EG vers RA et SD, RA vers SD, SD vers EX, CV vers RA, SD et EX sont listées explicitement.
- Chaque relation nomme son contrat publié, son producteur, son consommateur et le modèle interne qui ne doit pas être lu.
- Aucune relation implicite n'est acceptée.
- Les contrats détaillés ultérieurs doivent reprendre les noms de contrats publiés ici ou créer une nouvelle ADR si leur sens change.
- Les tests M-001 refusent un contexte manquant, une relation sans contrat, un propriétaire de données vide et une relation absente de la context map v4.1.

## Hors périmètre M-001

- Implémentation des comportements métier internes des contextes au-delà des contrats publiés M-001.
- Définition détaillée des schémas des relations marquées `Réservé`.
- Création de persistance opérationnelle, migration de données ou stockage concret.
- Implémentation d'UI, de connecteur externe ou d'adaptateur de plateforme.
- Extraction d'un bounded context en microservice.
