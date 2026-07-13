# T-022 - Publier le rapport d'exécution réelle

## Milestone

- Nom: M-013 - Durcissement et acceptation V1, tranche `M13-remediation`.
- Source: `docs/specs/plan_remediation_m13.md`, rapport d'acceptation V1 M-013 et exigences d'observabilité locale.
- Objectif métier: rendre auditable chaque run réel du pipeline, depuis le corpus PDF jusqu'à la réponse citée et aux refus explicites.

## Contexte DDD

- Domaine: assistant personnel de trading et d'investissement fondé sur preuves.
- Bounded context: `evaluation`, observabilité locale et gouvernance V1.
- Objectif métier: publier une preuve ouvrable de l'exécution réelle sans stocker de secret, prompt complet ou payload sensible.
- Langage ubiquitaire: rapport de run réel, hash PDF, version d'outil, métrique obligatoire, citation ouvrable, échec explicite, preuve de commande.
- Invariants critiques: aucun rapport GREEN sans run; chaque artefact critique porte un identifiant ou hash; les échecs sont reportés; les secrets et prompts complets sont exclus.
- Garde-fous: pas de correction manuelle des résultats; pas de rapport fabriqué; pas de payload sensible complet; pas de succès si une métrique obligatoire manque.

## Blocages Ou Préconditions

- État GREEN/RED connu: les rapports M-013 existants agrègent des preuves logicielles et LLM live; ils ne prouvent pas encore un run PDF -> réponse citée ouvrable.
- Présence des milestones amont dans master: M-003 à M-013 sont présents dans `master`; T-015 à T-021 doivent produire les preuves du run réel.
- Décisions manquantes: créer une ADR si le rapport de run devient un format durable d'audit partagé ou change la politique de rétention.
- Risques: rapport local non reproductible; secret dans un artefact; métriques incomplètes; correction manuelle; stockage de contenu documentaire privé en Git.

## Tâches

### T-022 - Publier le rapport d'exécution réelle

- But métier: rendre auditable chaque run réel du pipeline.
- Portée DDD: EV, observabilité, gouvernance V1, traçabilité des artefacts, métriques et diagnostics d'échec.
- Scénario BDD:
  - Given un run réel exécute corpus, recherche, réponse, chat et éventuellement stratégie.
  - When le run se termine.
  - Then un rapport conserve les identifiants, hashes, versions d'outils, métriques, citations et échecs sans stocker de secrets ni payloads sensibles complets.
- Tests d'acceptation à écrire: `uv run --locked gate`.
- Tests unitaires à écrire: version outil absente, hash PDF absent, citation non listée, métrique obligatoire absente, secret présent, échec non reporté, prompt complet stocké, rapport sans commande source.
- Implémentation attendue: produire `docs/evaluation/m013/real_pipeline_run_report.md` ou un artefact local équivalent contrôlé par gate, avec séparation explicite entre preuve versionnée et données privées locales.
- Invariants et garde-fous: aucun rapport GREEN sans run; aucun secret; aucun prompt complet; aucune correction manuelle des résultats; aucun effacement d'échec.
- Dépendances: T-015 à T-021, observabilité M-013, politiques de rétention existantes.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m013): couvrir rapport pipeline reel`
- Commit GREEN: `docs(m013): publier rapport pipeline reel`
