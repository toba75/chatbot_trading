# T-009 - Mesurer le LLM principal par le chemin réel

## Milestone
- Nom: M-012 - Évaluation pilote et calibration.
- Source: M-012, section `Évaluation du LLM principal` de la spécification v4.1.
- Objectif métier: comparer les checkpoints du modèle principal sur les tâches métier et le chemin d'inférence réel.

## Contexte DDD
- Domaine: évaluation scientifique et calibration des seuils.
- Bounded context: plateforme locale et RA/EG/SD évalués par M-012, sans donner au Spark de responsabilité métier.
- Objectif métier: mesurer les checkpoints Gemma via `docker-local -> llm-gateway -> réseau privé -> vLLM sur Spark`, avec métriques métier et techniques séparées.
- Langage ubiquitaire: checkpoint, benchmark LLM, sortie structurée, JSON valide, entailment, contradiction, tool calling, citation, latence gateway, TTFT, débit, retry, redémarrage Spark.
- Invariants critiques: le Spark reste sans état métier; un checkpoint communautaire n'est promu que s'il égale ou dépasse les checkpoints officiels; les sorties structurées invalides sont des échecs; les métriques techniques ne contiennent pas de prompts complets.
- Garde-fous: aucun appel direct au Spark depuis le domaine; aucun prompt complet dans les logs; aucun retry après réception du premier token; aucune promotion sur un chemin de test différent du chemin réel.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-008.
- Présence des milestones amont dans master: M-011 présent dans `master`.
- Décisions manquantes: ADR requise si le checkpoint de référence ou le profil de serving change une décision acceptée.
- Risques: comparer les modèles hors gateway; promouvoir un checkpoint communautaire sur une seule tâche; mélanger latence réseau et qualité métier dans un score unique.

## Tâches
### T-009 - Mesurer le LLM principal par le chemin réel
- But métier: choisir ou refuser un checkpoint principal sur preuves comparables.
- Portée DDD: `LlmBenchmarkSuite`, `CheckpointCandidate`, `StructuredOutputEvaluation`, mesures JSON, extraction atomique, négations, nombres, conditions, limites, entailment, contradiction, synthèse FR/EN, tool calling, citations et métriques techniques du chemin réel.
- Scénario BDD:
  - Given les checkpoints `nvidia/Gemma-4-31B-IT-NVFP4`, `YCWTG/gemma-4-31B-it-NVFP4A16-GPTQ` et `google/gemma-4-31B-it-qat-w4a16-ct`.
  - When ils sont évalués à travers le chemin réel d'inférence.
  - Then aucune promotion n'est possible sans métriques métier supérieures ou égales aux références officielles et sans métriques techniques exploitables.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue si un checkpoint exigé manque, si le chemin réel n'est pas attesté, si une tâche normative du benchmark LLM manque, si une sortie JSON invalide est comptée comme succès, si les métriques techniques mélangent prompts ou preuves complètes, ou si une promotion communautaire est acceptée sans comparaison suffisante sur toutes les tâches obligatoires.
- Tests unitaires à écrire: tests de calcul et décision pour checkpoint absent, chemin direct Spark interdit, JSON invalide, extraction atomique incomplète, négation perdue, nombre changé, condition d'application perdue, limite omise, entailment faux, contradiction non détectée, synthèse FR/EN dégradée, tool calling invalide, citation absente, retry borné avant premier token mesuré et idempotent, retry après premier token interdit, retry illimité refusé, métrique technique sensible, latence gateway absente, latence réseau absente, attente vLLM absente, TTFT absent, débit absent, taux d'erreur absent, taux de retry absent, stabilité des sorties structurées absente, redémarrage Spark non mesuré et promotion communautaire insuffisante.
- Implémentation attendue: créer la suite de benchmark LLM couvrant JSON valide, extraction atomique, négations, nombres, conditions d'application, limites, entailment, contradiction, synthèse FR/EN, tool calling et citations, les adaptateurs de mesure via gateway, les métriques techniques séparées du chemin réel, les fixtures de tâches métier, le rapport comparatif et la politique de promotion de checkpoint.
- Invariants et garde-fous: aucun secret ni payload complet dans les métriques; aucun accès direct Spark; aucune promotion si le chemin mesuré diffère du chemin V1; aucune promotion si une tâche normative LLM ou une métrique technique séparée manque; aucun fallback vers un autre modèle; aucune décision cachée dans la configuration.
- Dépendances: T-008; `app/platform`; `app/research_answering`; `app/evidence_governance`; ADR-007; ADR-008; ADR-009; DDD-ADR-007.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m012): couvrir le benchmark llm chemin reel`
- Commit GREEN: `feat(m012): mesurer le llm principal`
