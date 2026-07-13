# M-013 - Durcissement et acceptation V1

## Statut

- Milestone: M-013 - Durcissement et acceptation V1.
- Tâche source: `docs/tasks/milestone_013/0002_publier_specification_durcissement_v1.md`.
- Sources normatives: `docs/specs/plan_implementation_milestones_workstreams.md`, M-013; `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 18, 19, 20, 21, 22, 23 et 24; `docs/governance/m012_v1_gap_report.md`.
- Statut: spécification exécutable publiée pour guider T-003 à T-012.
- ADR applicables: ADR-007; ADR-008; ADR-009; ADR-010; ADR-013; DDD-ADR-004; DDD-ADR-006; DDD-ADR-010; DDD-ADR-011; DDD-ADR-012.
- ADR: non requise pour T-002; la présente spécification applique les décisions existantes sans imposer de nouvelle politique de rétention, sans rendre mTLS obligatoire et sans remplacer la topologie `docker-local` / `spark-inference`.

## Scénario BDD

- Given le système complet a été mesuré par M-012 et les critères V1 sont publiés.
- When la spécification M-013 est publiée.
- Then chaque comportement de durcissement nomme son invariant, son scénario BDD, son test RED, ses ADR applicables et sa commande de validation.

## Mission M-013

M-013 transforme les critères V1, les écarts M-012 et les exigences d'exploitation locale en gates testables. La mission ne déclare jamais une acceptation implicite: chaque critère V1 possède un test, une preuve ou un écart explicite, et un écart bloquant ou un écart non accepté interdit le verdict `acceptée` du `V1AcceptanceReport`.

M-013 consomme les preuves de SP, KA, EG, RA, CV, SD, EX, EV et `platform`. Elle ne prend pas possession des données métier de ces contextes et ne requalifie pas les tests scientifiques RED conservés par M-012.

## Contexte DDD

- Domaine: durcissement opérationnel et acceptation V1.
- Bounded context: gouvernance V1 transverse, avec `platform`, EV et tous les contextes métier comme producteurs de preuves.
- Intégrations: `platform` fournit sécurité réseau, pannes Spark, sauvegardes, monitoring et runbooks; EV fournit écarts et benchmarks M-012; les contextes métier fournissent les preuves d'acceptation fonctionnelle.
- Invariants: aucun critère V1 supprimé; aucun écart V1 sans statut exploitable; aucune décision d'acceptation sans preuve; aucun anti-pattern interdit ignoré; aucune documentation d'exploitation ne décrit un fallback non implémenté.

## Langage ubiquitaire M-013

| Terme | Sens M-013 | Invariant |
|---|---|---|
| V1AcceptanceGate | Gate transverse qui agrège critères V1, preuves, écarts et décisions. | Retourne GREEN uniquement si tous les critères sont satisfaits ou explicitement acceptés. |
| RegressionSuite | Suite de régression logicielle V1. | Couvre les comportements livrés sans transformer un test scientifique RED en succès scientifique. |
| SecurityAuditReport | Rapport d'audit réseau et sécurité Spark. | Prouve absence d'exposition publique, gateway unique et validation TLS. |
| BackupRestoreDrill | Exercice de sauvegarde chiffrée et restauration. | Produit `restore_test_result` et refuse une restauration non testée. |
| LocalMonitoringProfile | Profil local de monitoring d'exploitation. | Publie métriques sans prompts, preuves, réponses complètes ni secrets. |
| RetentionPolicy | Politique de conservation et purge administrative. | Conserve versions négatives et supersédées selon DDD-ADR-010 et fixe les durées V1 selon DDD-ADR-012. |
| Runbook | Procédure d'exploitation locale. | Décrit une action vérifiable sans fallback silencieux. |
| V1AcceptanceReport | Rapport final d'acceptation V1. | Référence preuves, commandes et écarts non acceptés avant toute décision. |
| écart non accepté | Écart V1 bloquant ou différé sans acceptation explicite. | Interdit l'acceptation V1. |

## Critères V1 et écarts M-012

M-013 reprend tous les critères V1 de la section 21 sans suppression. Le contrat d'entrée obligatoire est `docs/governance/m012_v1_gap_report.md`. Chaque critère V1 est relié à l'un des statuts suivants:

- `satisfait`: preuve M-012 ou M-013 suffisante;
- `bloquant`: interdit l'acceptation V1 tant qu'il n'est pas corrigé;
- `accepté`: accepté explicitement avec justification, preuve et responsabilité;
- `différé`: report visible, interdit l'acceptation si le report n'est pas accepté par le rapport final.

Aucune valeur de seuil non sourcée n'est créée par T-002. Les seuils et promotions restent ceux déjà publiés par M-012 ou par les tâches M-013 qui les justifieront.

## Statuts d'écarts V1

| Contexte | Statut M-012 | Décision M-013 | Commande de preuve | Blocage d'acceptation |
|---|---|---|---|---|
| SP | différé | Reprise par V1AcceptanceGate avec preuve ou acceptation explicite. | uv run --locked gate
| KA | différé | Reprise par V1AcceptanceGate avec preuve ou acceptation explicite. | uv run --locked gate
| EG | satisfait | Conservé comme preuve d'acceptation. | uv run --locked gate
| RA | différé | Reprise par V1AcceptanceGate avec preuve ou acceptation explicite. | uv run --locked gate
| CV | satisfait | Conservé comme preuve d'acceptation. | uv run --locked gate
| SD | bloquant | Correction obligatoire avant acceptation V1. | uv run --locked gate
| LLM | bloquant | Correction obligatoire avant acceptation V1. | uv run --locked gate
| EX | satisfait | Conservé comme preuve d'acceptation. | uv run --locked gate

## Objets de gouvernance M-013

| Objet | Responsabilité | Invariant |
|---|---|---|
| V1AcceptanceGate | Agréger les preuves, écarts et décisions V1. | Aucun critère V1 ne sort de la gate. |
| RegressionSuite | Prouver les non-régressions logicielles V1. | Les tests scientifiques RED restent visibles. |
| SecurityAuditReport | Publier l'audit réseau et sécurité. | Le Spark reste inaccessible hors `llm-gateway`. |
| BackupRestoreDrill | Prouver sauvegarde chiffrée et restauration. | `restore_test_result` est requis. |
| LocalMonitoringProfile | Publier le monitoring local. | Aucun payload sensible dans logs ou métriques. |
| RetentionPolicy | Décrire conservation et purge explicite. | Les versions négatives et supersédées restent conservées selon DDD-ADR-010 et les durées V1 restent explicites selon DDD-ADR-012. |
| Runbook | Décrire les opérations locales. | Chaque procédure nomme commande, preuve et erreur explicite. |
| V1AcceptanceReport | Publier le verdict V1. | Tout écart non accepté bloque le verdict. |

## Politiques d'acceptation V1

| Politique | Décision | Invariants | ADR |
|---|---|---|---|
| V1AcceptanceGatePolicy | Agrège critères, preuves, écarts et décisions. | Aucun GREEN si écart bloquant ou preuve absente. | ADR-010; DDD-ADR-010 |
| RegressionSuitePolicy | Contrôle les non-régressions logicielles. | Un test scientifique RED n'est pas masqué par un test logiciel GREEN. | ADR-010 |
| SecurityAuditPolicy | Vérifie la frontière `docker-local` / `spark-inference`. | Aucun port public, navigateur incapable d'appeler le Spark, gateway unique. | ADR-007; ADR-008; ADR-009 |
| BackupRestorePolicy | Exige sauvegarde chiffrée et restauration testée. | Le rapport contient `restore_test_result` avant acceptation et le manifeste distingue autorité métier et projection régénérable. | ADR-009; ADR-013; DDD-ADR-004; DDD-ADR-010 |
| RetentionPolicy | Encadre conservation et purge administrative. | Les durées et opérations de purge administrative sont explicites; aucune purge ordinaire ne supprime les preuves défavorables. | DDD-ADR-010; DDD-ADR-012 |
| MonitoringPolicy | Publie les signaux d'exploitation locaux. | Aucun prompt, preuve, réponse complète ou secret dans les signaux. | ADR-008; ADR-009 |
| RunbookPolicy | Publie des procédures d'exploitation vérifiables. | Aucun fallback silencieux documenté. | ADR-010 |
| UserDocumentationPolicy | Publie le comportement utilisateur V1. | Les statuts, citations et limites sont visibles. | ADR-010 |
| ForbiddenAntiPatternPolicy | Contrôle les anti-patterns V1. | Chaque anti-pattern interdit est testé ou revu. | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-010 |
| V1AcceptanceReportPolicy | Produit le verdict final. | Les décisions référencent preuves, commandes et écarts. | ADR-010; DDD-ADR-011 |

## Sécurité réseau Spark

M-013 vérifie les exigences de la section 18 et des ADR-007, ADR-008 et ADR-009:

- les ports de `docker-local` sont liés à `127.0.0.1` par défaut;
- aucun port PostgreSQL, Qdrant, worker, Granite ou vLLM n'est exposé publiquement;
- le seul chemin applicatif vers vLLM passe par `llm-gateway`;
- le navigateur ne peut pas appeler directement le Spark;
- TLS et validation stricte du certificat Spark sont obligatoires;
- aucune désactivation automatique de TLS n'est autorisée;
- le Spark ne conserve aucun corpus, conversation, claim, stratégie, expérience ou résultat durable.

La spécification T-002 ne rend pas mTLS obligatoire. Si une tâche M-013 transforme mTLS en profil obligatoire, elle doit créer une ADR.

## Sauvegarde et restauration

Le `BackupRestoreDrill` couvre les données durables de `docker-local`: PostgreSQL, Qdrant comme projection régénérable, corpus, expériences, rapports d'évaluation et artefacts de gouvernance. Le Spark est traité selon ADR-009 comme sans état métier durable.

Chaque exercice publie:

- manifeste de sauvegarde `M013-BackupManifest-1.0` selon ADR-013;
- périmètre sauvegardé;
- commande de sauvegarde;
- preuve de chiffrement;
- cible de restauration isolée;
- `restore_test_result`;
- écarts et corrections éventuels.

Une sauvegarde non restaurée ne suffit pas pour accepter V1.

## Rétention

La `RetentionPolicy` applique DDD-ADR-010 et DDD-ADR-012: claims rejetés, réponses supersédées, stratégies invalides, versions remplacées, expériences échouées et résultats défavorables restent conservés. Une purge administrative doit être explicite, justifiée, auditée et compatible avec la lecture pendant la durée publiée.

La V1 conserve les artefacts d'autorité hors conversation pendant 120 mois, les conversations pendant 18 mois et les projections régénérables pendant 3 mois. Aucune purge ordinaire n'est autorisée. Une purge de conversation ne cascade pas vers KA, EG, RA, SD ou EX. Une projection régénérable peut être purgée seulement avec une reconstruction documentée depuis les artefacts d'autorité conservés.

## Monitoring local

Le `LocalMonitoringProfile` relie les signaux des sections 19 et 20 aux preuves V1:

- disponibilité `spark-inference`, DNS, TCP, TLS et authentification;
- latence gateway, latence réseau, attente vLLM, temps jusqu'au premier token et débit;
- erreurs et retries avant premier token;
- ouverture et fermeture du circuit breaker;
- ressources `docker-local` CPU, mémoire, I/O, stockage et files de jobs;
- absence de prompts complets, preuves complètes, réponses complètes, secrets et données de marché complètes.

Le monitoring est local et ne publie pas de métriques vers un fournisseur externe.

## Runbooks

Les `Runbook` M-013 couvrent au minimum:

- démarrage et arrêt local;
- vérification réseau Spark;
- rotation et validation de certificat;
- panne Spark avant génération;
- coupure après premier token;
- sauvegarde chiffrée;
- restauration testée;
- purge administrative;
- lecture du rapport d'acceptation.

Chaque runbook indique une commande, un résultat attendu, une erreur explicite et une preuve à conserver. Aucun runbook ne décrit un fallback silencieux ou un fournisseur distant de secours.

## Documentation utilisateur

La documentation utilisateur explique les capacités V1 sans promettre une acceptation implicite:

- conversation locale;
- citations ouvrables;
- statuts documentaire et scientifique;
- stratégie candidate attribuée;
- expérience reproductible;
- limites liées aux écarts V1;
- lecture du `V1AcceptanceReport`.

La documentation utilisateur ne doit pas exposer de secret, prompt complet, preuve complète, réponse complète ou donnée de marché complète.

## Anti-patterns interdits V1

M-013 contrôle les anti-patterns de la section 23, notamment:

- Conversation utilisée comme source factuelle;
- score de similarité traité comme preuve;
- affirmation vérifiée sans span direct;
- règle de stratégie sans origine;
- paramètre inventé silencieusement;
- résultat négatif supprimé;
- version publiée modifiée en place;
- accès direct d'un contexte métier au protocole vLLM;
- bounded contexts ou bases déployés sur le Spark;
- navigateur ou interface appelant directement le Spark;
- service Gemma caché dans le Compose local comme fallback non déclaré;
- retry illimité d'une génération distante;
- journalisation persistante des prompts complets sur le Spark.

Chaque anti-pattern interdit doit être couvert par un test, une validation statique ou une revue documentée avant `V1AcceptanceReport`.

La preuve T-011 est `docs/governance/m013_antipattern_review.md`, contrôlée par `uv run --locked gate` et par `gate_tests/ported/tests/m013/validate_v1_antipatterns_acceptance.py`. Les questions ouvertes de la section 23 restent ouvertes contrôlées tant qu'une ADR ne les résout pas explicitement.

## Rapport d'acceptation V1

Le `V1AcceptanceReport` contient:

- version de la spécification M-013;
- liste des critères V1;
- preuves par critère;
- commandes exécutées;
- décisions et ADR applicables;
- écarts satisfaits, acceptés, différés ou bloquants;
- liste des écarts non acceptés;
- verdict final.

Le verdict final est refusé si un écart bloquant existe, si un écart différé n'est pas accepté explicitement, si une commande de preuve est absente ou si une ADR requise par une nouvelle décision structurante manque.

## Comportements vérifiables M-013

| Comportement | Invariant | Scénario BDD | Test RED | ADR | Commande |
|---|---|---|---|---|---|
| V1-001 - Spécification exécutable M-013 | La spécification nomme mission, critères V1, écarts M-012, sécurité, sauvegarde, restauration, rétention, monitoring, runbooks, documentation, anti-patterns, rapport d'acceptation, ADR et commandes. | Given le système complet a été mesuré par M-012 et les critères V1 sont publiés; When la spécification M-013 est publiée; Then chaque comportement de durcissement nomme invariant, scénario BDD, test RED, ADR et commande. | T-002 | ADR-007; ADR-008; ADR-009; ADR-010; DDD-ADR-006; DDD-ADR-010; DDD-ADR-011 | uv run --locked gate
| V1-002 - Contrôle des écarts V1 M-012 | Chaque écart M-012 a un statut exploitable et les bloquants interdisent l'acceptation. | Given le rapport d'écarts M-012 est publié; When V1AcceptanceGate lit les écarts; Then tout écart bloquant ou non accepté bloque le verdict. | T-003 | ADR-010; DDD-ADR-010; DDD-ADR-011 | uv run --locked gate
| V1-003 - Suite de régression V1 | La RegressionSuite couvre les comportements livrés sans masquer les tests scientifiques RED. | Given les comportements M-000 à M-012 sont livrés; When la suite de régression V1 est exécutée; Then les tests logiciels passent et les écarts scientifiques restent visibles. | T-004 | ADR-010; DDD-ADR-011 | uv run --locked gate
| V1-004 - Audit réseau et sécurité Spark | Le Spark est accessible uniquement depuis llm-gateway et aucune donnée métier durable n'y réside. | Given docker-local et spark-inference sont configurés; When SecurityAuditReport est produit; Then aucun port public, accès navigateur direct ou stockage métier Spark n'est accepté. | T-005 | ADR-007; ADR-008; ADR-009 | uv run --locked gate
| V1-005 - Pannes Spark sans fallback | Une panne Spark produit un état explicite sans corruption d'état. | Given une demande nécessitant Gemma; When le Spark est indisponible ou le flux est coupé; Then LLM_UNAVAILABLE ou l'erreur TLS explicite est publiée sans fallback silencieux. | T-006 | ADR-008; ADR-009; DDD-ADR-006 | uv run --locked gate
| V1-006 - Sauvegarde chiffrée et restauration testée | BackupRestoreDrill produit une preuve de restauration avant acceptation. | Given les données docker-local sont sauvegardées; When la restauration isolée est exécutée; Then restore_test_result prouve la restauration chiffrée et exploitable. | T-007 | ADR-009; ADR-013; DDD-ADR-004; DDD-ADR-010 | uv run --locked gate
| V1-007 - Rétention et purge administrative | Les versions négatives et supersédées restent consultables. | Given des artefacts négatifs ou supersédés existent; When la rétention est validée; Then aucune purge implicite ne les supprime. | T-008 | DDD-ADR-010; DDD-ADR-012 | uv run --locked gate
| V1-008 - Monitoring local d'exploitation | LocalMonitoringProfile publie les signaux sans payload sensible. | Given la plateforme locale est exécutée; When les métriques sont collectées; Then latence, erreurs, ressources et circuit breaker sont visibles sans secrets ni contenus complets. | T-009 | ADR-008; ADR-009; ADR-010 | uv run --locked gate
| V1-009 - Runbooks et documentation utilisateur | Les procédures et la documentation décrivent des actions vérifiables sans fallback. | Given l'utilisateur exploite la V1 locale; When il lit runbooks et documentation; Then chaque action sensible nomme commande, résultat attendu, erreur explicite et preuve. | T-010 | ADR-010 | uv run --locked gate
| V1-010 - Anti-patterns interdits V1 | Chaque anti-pattern interdit est testé ou revu. | Given les anti-patterns section 23 sont publiés; When la revue M-013 est exécutée; Then aucun anti-pattern interdit n'est ignoré. | T-011 | ADR-007; ADR-008; ADR-009; DDD-ADR-006; DDD-ADR-010 | uv run --locked gate
| V1-011 - Rapport d'acceptation V1 | V1AcceptanceReport référence preuves, commandes, décisions et écarts. | Given toutes les preuves M-013 sont produites; When le rapport d'acceptation est publié; Then le verdict refuse tout écart bloquant ou non accepté. | T-012 | ADR-010; DDD-ADR-010; DDD-ADR-011 | uv run --locked gate

## Commandes de validation

```console
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
uv run --locked gate
```

## Exclusions M-013

- T-002 ne corrige pas les écarts V1 M-012 et ne produit pas le rapport final d'acceptation.
- T-002 ne fixe pas de nouvelle durée de rétention.
- T-002 ne rend pas mTLS obligatoire.
- T-002 ne remplace pas la topologie `docker-local` / `spark-inference`.
- Aucun fallback silencieux n'est autorisé dans M-013.
- Aucun critère V1 n'est supprimé.
- Aucun prompt complet, preuve complète, réponse complète, secret ou donnée de marché complète n'est publié comme preuve d'exploitation.
