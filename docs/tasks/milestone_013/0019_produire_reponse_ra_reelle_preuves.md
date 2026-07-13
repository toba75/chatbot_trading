# T-019 - Produire une réponse RA réelle fondée sur preuves

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, écarts V1 RA et règles de gouvernance des preuves.
- Objectif métier: prouver qu'une réponse factuelle publiée sort uniquement si les preuves du corpus réel la supportent, la qualifient ou justifient une abstention.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `research_answering` et `evidence_governance`, avec dépendances vers `knowledge_access` et `platform.llm_gateway`.
- Objectif métier: assembler les preuves réelles, produire ou refuser une réponse, puis vérifier les assertions avant publication.
- Langage ubiquitaire: preuve candidate, preuve scellée, claim vérifié, réponse vérifiée, abstention, citation ouvrable, statut documentaire.
- Invariants critiques: aucune réponse factuelle sans preuve; chaque claim est supporté, partiellement supporté, conflictuel ou refusé; chaque citation remonte au PDF original.
- Garde-fous: pas de mémoire conversationnelle utilisée comme preuve; pas de statut documentaire inventé; pas de fallback LLM; pas de réponse plausible sans citation ouvrable.

## Blocages Ou Préconditions

- État GREEN/RED connu: RA reste en écart différé dans le rapport V1; T-018 doit fournir des candidats KA réels et résolubles.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; les règles EG déjà acceptées doivent être consommées plutôt que réécrites.
- Décisions manquantes: aucune si les statuts documentaires existants sont repris; créer une ADR seulement si la classification des réponses vérifiées change.
- Risques: assertion non supportée publiée; contradiction ignorée; abstention attendue non produite; citation non ouvrable; Spark indisponible transformé en réponse générique.

## Tâches

### T-019 - Produire une réponse RA réelle fondée sur preuves

- But métier: prouver qu'une réponse factuelle ne sort que si les preuves du corpus réel la supportent.
- Portée DDD: RA, EG, preuves scellées, claims, statuts documentaires, citations et génération via `llm-gateway`.
- Scénario BDD:
  - Given une question annotée possède des preuves attendues dans le corpus réel.
  - When RA répond à la question.
  - Then la réponse est supportée, partiellement supportée, conflictuelle ou abstinente selon les preuves réelles, avec citations ouvrables.
- Tests d'acceptation à écrire: `uv run --locked gate`.
- Tests unitaires à écrire: assertion non supportée, citation absente, citation non ouvrable, obligation de recherche manquante, contradiction ignorée, abstention attendue non produite, réponse LLM publiée malgré échec de preuve.
- Implémentation attendue: orchestrer RA avec KA réel, EG réel et `llm-gateway` réel pour la génération, puis vérifier les assertions avant publication.
- Invariants et garde-fous: aucune réponse plausible sans preuve; aucun fallback vers mémoire conversationnelle; aucun statut documentaire inventé; aucune publication factuelle si Spark ou KA échoue.
- Dépendances: T-018, `llm-gateway`, Spark, règles EG et RA existantes.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir reponse verifiee reelle`
- Commit GREEN: `feat(m013): produire reponse reelle citee`
