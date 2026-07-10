# T-020 - Valider le chat produit réel

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, contrats CV M-008 et tranche `M13-reality`.
- Objectif métier: prouver que l'utilisateur interagit avec le pipeline produit réel via le contrat conversationnel, et non avec un endpoint LLM simplifié.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `conversation`, `research_answering`, `knowledge_access`, `evidence_governance` et `platform`.
- Objectif métier: faire traverser un tour conversationnel local complet, depuis `/v1/chat/completions` jusqu'aux preuves réelles et à Gemma via `llm-gateway`.
- Langage ubiquitaire: conversation locale, tour CV, mode justifié, réponse conversationnelle citée, citation ouvrable, endpoint public local, absence de contournement.
- Invariants critiques: un chat produit crée un tour CV; RA n'est pas contourné pour une question factuelle; Spark n'est jamais appelé directement; les citations sont exposées à l'utilisateur.
- Garde-fous: pas de chat générique; pas de prompt produit codé en dur comme preuve; pas de réponse sans tour CV; pas de réponse factuelle sans preuve ouvrable.

## Blocages Ou Préconditions

- État GREEN/RED connu: `M13-reality` prouve déjà un chemin LLM live et un endpoint chat minimal; T-019 doit prouver la réponse RA réelle fondée sur preuves.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; M-008 fournit le contrat conversationnel à respecter.
- Décisions manquantes: aucune si l'endpoint existant est relié aux cas d'usage CV; créer une ADR seulement si le contrat public chat change.
- Risques: endpoint `/v1/chat/completions` limité au LLM; historique conversationnel utilisé comme preuve; Spark appelé directement; citations présentes en interne mais non exposées.

## Tâches

### T-020 - Valider le chat produit réel

- But métier: prouver que l'utilisateur interagit avec le pipeline réel via le contrat conversationnel.
- Portée DDD: CV, RA, KA, EG, platform, endpoint `/v1/chat/completions`, routage de mode et exposition des citations.
- Scénario BDD:
  - Given un utilisateur pose une question en langage naturel dans une conversation locale.
  - When `/v1/chat/completions` traite la demande.
  - Then le tour CV est créé, le mode est justifié, RA récupère les preuves réelles, Gemma répond via `llm-gateway`, et la réponse expose les citations ouvrables.
- Tests d'acceptation à écrire: `tests/m013/validate_real_chat_pipeline_acceptance.ps1`.
- Tests unitaires à écrire: conversation absente, idempotence absente, mode injustifié, RA contourné, citation non exposée, Spark appelé directement, réponse factuelle sans preuve.
- Implémentation attendue: relier l'orchestrateur local au vrai handler CV et à ses ports applicatifs au lieu d'un endpoint chat simplifié limité au LLM.
- Invariants et garde-fous: pas de chat générique; pas de réponse sans tour CV; pas de prompt produit codé en dur comme preuve; pas d'accès direct à Spark.
- Dépendances: T-019, endpoint CV M-008, `llm-gateway`, Spark.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m013\validate_real_chat_pipeline_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_task_system.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m013): couvrir chat pipeline reel`
- Commit GREEN: `feat(m013): brancher chat produit sur pipeline reel`
