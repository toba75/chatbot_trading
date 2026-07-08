# Guide utilisateur V1 M-013

## Statut

- Identifiant: `M013-UserDocumentation-1.0`
- Tâche: `docs/tasks/milestone_013/0010_publier_runbooks_documentation_utilisateur.md`
- Index: `docs/governance/m013_documentation_index.md`
- ADR applicables: ADR-010
- ADR: non requise; ce guide applique les décisions publiées sans nouvelle topologie ni nouvelle politique.
- statuts publics.
- limites V1.
- aucun secret.
- aucun fallback silencieux.
- aucune promesse financière.
- aucun conseil d'investissement.

## Scénario BDD

- Given l'utilisateur exploite la V1 localement.
- When il consulte conversation locale, citations, statuts, stratégie candidate, expérience reproductible et écarts.
- Then chaque capacité visible porte son statut, sa preuve ou sa limite sans acceptation implicite.

## Capacités V1

| Capacité | Ce que l'utilisateur peut faire | Preuve ou limite |
|---|---|---|
| conversation locale | Poser une question et suivre un fil append-only. | Les faits viennent des citations et réponses vérifiées, pas de l'historique brut. |
| citations ouvrables | Ouvrir les références associées aux réponses. | `SourceLocator` et statuts de support restent visibles. |
| recherche approfondie | Demander une synthèse multi-sources. | Couverture insuffisante et contradictions sont affichées. |
| stratégie candidate attribuée | Lire règles, origines, paramètres et diagnostics. | SD reste bloquant si les paramètres n'ont pas de plan de calibration. |
| expérience reproductible | Lire coûts, hypothèses, période, univers et résultat. | Les résultats négatifs ou échoués restent conservés. |
| monitoring local | Lire santé, erreurs, latence, Spark, sauvegarde, restauration et écarts. | Aucun export externe ni endpoint public. |

## Statuts publics

| Statut public | Sens utilisateur |
|---|---|
| `SUPPORTED` | Les citations directes supportent la réponse. |
| `PARTIALLY_SUPPORTED` | La réponse est partiellement supportée et ses limites sont visibles. |
| `INSUFFICIENT_EVIDENCE` | Les preuves sont insuffisantes; l'abstention est attendue. |
| `CONFLICTING_EVIDENCE` | Des preuves contradictoires empêchent une conclusion simple. |
| `LLM_UNAVAILABLE` | Spark est indisponible avant génération complète. |
| `LLM_PARTIAL_OUTPUT` | Une sortie partielle n'est pas publiable comme fait. |
| `BLOCKED` | Un écart bloquant ou une preuve absente interdit l'acceptation V1. |

## Limites V1 et écarts V1

| Contexte | Statut | Impact utilisateur |
|---|---|---|
| SP | différé | Qualité documentaire, cellules, formules, temps, mémoire et stabilité restent visibles avant acceptation. |
| KA | différé | Recall pilote sous seuil; les résultats de recherche peuvent être insuffisants. |
| RA | différé | Abstention et réponses vérifiées doivent rester qualifiées. |
| SD | bloquant | Les paramètres sans plan de calibration bloquent l'acceptation V1. |
| LLM | bloquant | Le checkpoint principal n'est pas promu sur toutes les tâches obligatoires. |
| EG | satisfait | Gouvernance des preuves acceptée. |
| CV | satisfait | Conversation locale et statuts produit acceptés. |
| EX | satisfait | Backtests pilotes reproductibles et résultats négatifs conservés. |

## Lecture opérationnelle

- Démarrage local et arrêt: `docs/runbooks/exploitation_locale.md`.
- Sauvegarde et restauration: `docs/runbooks/sauvegarde_restauration.md`.
- Audit réseau et panne Spark: `docs/runbooks/spark_reseau_incidents.md`.
- Monitoring local: `docs/runbooks/monitoring_local.md`.
- Ingestion PDF: `docs/runbooks/ingestion_pdf.md`.
- Conversation V1: `docs/runbooks/conversation_v1.md`.
- Recherche approfondie: `docs/runbooks/recherche_approfondie.md`.
- Stratégie et backtest: `docs/runbooks/strategie_backtest.md`.

## Garde-fous utilisateur

- Les résultats de stratégie et backtest sont des mesures pilotes descriptives.
- Aucune promesse financière.
- Aucun conseil d'investissement.
- Aucun secret, prompt complet, preuve complète, réponse complète ou donnée de marché complète n'est publié.
- Aucun fallback silencieux: une panne ou une limite produit un statut public explicite.
- Les services internes restent locaux et non publiés.
