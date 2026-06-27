# T-006 - Encoder la projection en dense et sparse

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 embeddings, recherche sparse, projection reconstruisible et versions de modèles journalisées.
- Objectif métier: préparer les chunks à la recherche hybride sans imposer une méthode unique de rappel documentaire.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: produire des représentations dense et sparse versionnées pour les chunks éligibles.
- Langage ubiquitaire: `DenseEncoder`, `SparseEncoder`, version de modèle, profil sparse, vecteur dense, vecteur sparse, trace d'encodage.
- Invariants critiques: les versions de modèles et paramètres sont obligatoires; un échec d'encodage n'autorise pas une recherche partielle silencieuse; les vecteurs sont régénérables.
- Garde-fous: pas de modèle implicite; pas de vecteur sans chunk source; pas de mélange dense/sparse non tracé; pas d'appel Spark pour embeddings sans ADR.

## Blocages Ou Préconditions
- État GREEN/RED connu: chunks et métadonnées disponibles après T-004 et T-005.
- Présence des milestones amont dans master: M-002 garantit les frontières réseau; M-004 garantit le contenu canonique.
- Décisions manquantes: ADR obligatoire si les embeddings sont déplacés vers le Spark, car la cible actuelle réserve le Spark à Gemma via vLLM.
- Risques: score dense interprété comme vérité; encodage incomplet accepté; versions de modèles impossibles à auditer.

## Tâches
### T-006 - Encoder la projection en dense et sparse
- But métier: fournir à la recherche hybride les représentations nécessaires pour retrouver concepts et termes exacts.
- Portée DDD: ports `DenseEncoder` et `SparseEncoder`, résultats d'encodage versionnés, erreurs explicites et intégration au `BuildFingerprint`.
- Scénario BDD:
  - Given des chunks éligibles avec métadonnées et profil d'encodage explicite.
  - When KA encode la projection.
  - Then chaque chunk possède un résultat dense et sparse versionné ou la projection échoue avec un code explicite.
- Tests d'acceptation à écrire: `tests/m005/validate_projection_encoding_acceptance.ps1`, couvrant encodage dense+sparse, version obligatoire, refus d'encodage partiel et absence d'appel Spark.
- Tests unitaires à écrire: tests de ports encodeurs, résultat d'encodage, erreurs `DENSE_ENCODING_FAILED`, `SPARSE_ENCODING_FAILED`, version manquante et empreinte de build.
- Implémentation attendue: créer les ports d'encodage KA et un orchestrateur d'encodage testable avec doubles déterministes.
- Invariants et garde-fous: pas de fallback dense vers sparse ni sparse vers dense; pas de valeur de modèle par défaut; pas de stockage de texte documentaire complet dans les logs d'encodage.
- Dépendances: T-005; ADR-005; ADR-007; ADR-009; DDD-ADR-004.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_encoding_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m005\validate_projection_encoding_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\validate_network_boundary.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m005): couvrir l encodage dense sparse`
- Commit GREEN: `feat(m005): encoder la projection dense sparse`
