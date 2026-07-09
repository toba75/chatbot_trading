# ADR-015 - Provenance LLM déclarée par le gateway

**Statut :** Acceptée
**Date :** 2026-07-09
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/m013_reality_closure.md`; `docs/tasks/milestone_013/0013_ancrer_gateway_llm_chemin_reel.md`; test local du NIM Gemma sur `192.168.1.120:8000`

## Contexte

Le conteneur NIM Gemma sur Spark expose une API compatible OpenAI et répond aux inférences structurées. La réponse observée contient le modèle servi et le fingerprint runtime, mais ne fournit pas les champs applicatifs stables `model_revision` et `runtime_version` attendus par le gateway M-002.

M-013 interdit de considérer la V1 acceptée tant que le chemin LLM principal reste bloquant. Autoriser une inférence réussie sans provenance exploitable casserait les exigences de traçabilité M-012/M-013. Inventer une provenance depuis le modèle servi, le digest Docker ou l'heure d'appel serait un fallback silencieux.

ADR-014 conserve l'endpoint Docker Spark externe sans clé API. Cette ADR précise uniquement la provenance applicative exigée par le gateway.

## Décision

Le gateway LLM DOIT recevoir une provenance modèle déclarée explicitement par configuration locale.

La configuration du gateway DOIT contenir:

- `GEMMA_MODEL_REVISION`, révision ou identifiant opérationnel du modèle servi;
- `GEMMA_RUNTIME_VERSION`, version ou identifiant opérationnel du runtime de serving.

Ces valeurs NE DOIVENT PAS avoir de valeur par défaut. Elles NE DOIVENT PAS être inférées depuis `GEMMA_MODEL`, depuis l'URL Spark, depuis le digest Docker ou depuis un fingerprint non normalisé.

Quand la réponse OpenAI compatible fournit `model_revision` ou `runtime_version` dans le payload ou les headers, ces valeurs PEUVENT être utilisées seulement si elles sont présentes et normalisées. Quand le NIM ne les fournit pas, le gateway DOIT utiliser la provenance déclarée explicitement dans sa configuration.

Une inférence réussie sans provenance complète DOIT échouer avec une erreur explicite. Une inférence échouée PEUT journaliser une provenance absente, car elle ne produit pas de résultat métier publiable.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Exiger que NIM fournisse les champs de provenance | Rejetée | Le conteneur réel ne les renvoie pas aujourd'hui et le projet doit rester compatible avec ce runtime local. |
| Inférer la provenance depuis le nom du modèle | Rejetée | Mélange modèle servi et révision effective; ce serait une valeur implicite. |
| Déclarer la provenance côté gateway sans valeur par défaut | Retenue | Rend le chemin réel exploitable, auditable et cohérent avec l'absence de fallback. |

## Conséquences

### Positives

- Les évaluations aval peuvent relier chaque inférence réussie à un modèle et un runtime explicites.
- Le gateway peut fonctionner avec le NIM Spark actuel sans exiger de secret ou header fictif.
- L'observabilité gateway conserve les dimensions de modèle nécessaires aux rapports V1.

### Négatives ou coûts

- L'exploitant local doit fournir deux variables de configuration supplémentaires.
- Une configuration incomplète bloque le démarrage ou l'inférence réelle.
- Une rotation de modèle ou d'image impose de mettre à jour la provenance déclarée avant les benchmarks.

### Risques et contrôles

- Risque: provenance déclarée obsolète après redéploiement Spark. Contrôle: runbook et benchmark live M13-reality doivent publier la valeur utilisée.
- Risque: confusion entre modèle et runtime. Contrôle: deux champs distincts et obligatoires.
- Risque: contournement par valeurs placeholder. Contrôle: tests de configuration et rapports V1 refusant les champs vides ou non normalisés.

## Impact d'implémentation

- Modules concernés: `app/platform/llm_gateway/__init__.py`, `app/platform/observability/__init__.py`.
- Configuration concernée: `GEMMA_MODEL_REVISION`, `GEMMA_RUNTIME_VERSION`.
- Tests attendus: test live M13-reality du gateway Spark réel; tests unitaires M-002 de provenance déclarée; validations ADR.
- Milestones concernées: M-002, M-012, M-013.

## Liens de traçabilité

- Spécification: `docs/specs/m013_reality_closure.md`.
- Plan d'implémentation: M-013, tranche `M13-reality`, T-013.
- Tests d'acceptation: `tests/m013/validate_llm_gateway_real_spark_acceptance.ps1`.
- Commits: RED et GREEN à renseigner après livraison.

## Notes

Cette décision ne change pas la frontière réseau ADR-014: le seul chemin applicatif vers Spark reste `llm-gateway -> spark-inference`, sans clé API pour le conteneur actuel.
