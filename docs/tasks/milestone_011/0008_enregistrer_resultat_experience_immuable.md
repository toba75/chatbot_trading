# T-008 - Enregistrer un résultat d'expérience immuable

## Milestone
- Nom: M-011 - Expérience reproductible.
- Source: M-011, contrat `ExperimentResult`, registre append-only des expériences et relation EX -> RA/CV.
- Objectif métier: conserver la sortie d'expérience comme résultat publié, hashé et immuable sans perdre l'historique de l'agrégat `Experiment`.

## Contexte DDD
- Domaine: expérimentation quantitative reproductible.
- Bounded context: EX, publiant `ExperimentResult` vers RA et CV.
- Objectif métier: transformer la sortie moteur en `ExperimentResult` append-only, consultable et rattaché aux entrées figées, tout en conservant la transition terminale de l'expérience.
- Langage ubiquitaire: `Experiment`, `ExperimentRepository`, `ExperimentResult`, `result_hash`, métriques, séries temporelles, positions, transactions, avertissements, logs, diagnostics, artefacts, statut `COMPLETED`, statut `FAILED`, cause explicite, registre append-only.
- Invariants critiques: `COMPLETED` exige un résultat et un hash; `FAILED` exige une cause explicite; les séries temporelles, positions, transactions, avertissements, logs et artefacts ont une référence hashée ou une empreinte; les métriques restent interprétables avec période, benchmark, univers, coûts et hypothèses; la chronologie `frozen_at -> started_at -> completed_at` est cohérente; aucune expérience terminale ne peut être supprimée ou réécrite.
- Garde-fous: pas d'écrasement de résultat ou d'expérience; pas de résultat échoué sans cause; pas de métrique non finie; pas de métrique sans contexte d'interprétation; pas de sortie volumineuse non référencée par hash; pas de statut terminal sans événement.

## Blocages Ou Préconditions
- État GREEN/RED connu: dépend de T-007.
- Présence des milestones amont dans master: M-010 présent dans `master`; le contrat `ExperimentResult` existe depuis M-001.
- Décisions manquantes: aucune.
- Risques: stocker des artefacts hors base sans hash; oublier séries temporelles, positions, transactions, avertissements ou logs; oublier la cause d'échec; croire que le résultat append-only suffit sans registre append-only de l'expérience; publier un résultat avec entrées incohérentes ou métriques sans période, benchmark, univers, coûts et hypothèses.

## Tâches
### T-008 - Enregistrer un résultat d'expérience immuable
- But métier: publier un résultat EX fiable pour interprétation par RA et présentation par CV.
- Portée DDD: commandes `CompleteExperiment` et `FailExperiment`, port `ExperimentRepository`, port `ExperimentResultRepository`, port `ExperimentArtifactStore`, registre append-only des expériences, contrat `ExperimentResult`, événements `ExperimentCompleted` et `ExperimentFailed`, hash de résultat, métriques interprétables, séries temporelles, positions, transactions, avertissements, logs et artefacts hashés.
- Scénario BDD:
  - Given une expérience `RUNNING` a produit une sortie moteur ou une erreur déterministe.
  - When EX clôt l'expérience.
  - Then un `ExperimentResult` immuable est enregistré avec entrées figées, métriques interprétables ou cause d'échec, séries temporelles, positions, transactions, avertissements, logs, hash de résultat, artefacts hashés et événement terminal.
- Tests d'acceptation à écrire: `uv run --locked gate`, qui échoue tant qu'un résultat peut être modifié, qu'une expérience terminale peut être supprimée ou réécrite, qu'un échec peut être enregistré sans cause, qu'un hash manque, qu'une métrique non finie est acceptée, qu'une métrique manque de période, benchmark, univers, coûts ou hypothèses, qu'une série temporelle, position, transaction, avertissement ou log attendu n'est pas conservé par valeur ou référence hashée, ou qu'une chronologie incohérente passe.
- Tests unitaires à écrire: tests de `ExperimentRepository`, `ExperimentResultRepository`, `ExperimentArtifactStore`, `CompleteExperimentHandler`, `FailExperimentHandler`, `ExperimentCompleted`, `ExperimentFailed`, hash déterministe, artefacts absents, séries temporelles absentes, positions absentes, transactions absentes, avertissements absents, logs absents, contexte de métrique absent, statut terminal interdit, suppression d'expérience, réécriture de transition terminale et cohérence avec le contrat M-001.
- Implémentation attendue: étendre le registre append-only en mémoire des expériences, assembler `ExperimentResult` depuis la sortie moteur, enregistrer métriques avec période, benchmark, univers, coûts et hypothèses, conserver séries temporelles, positions, transactions, avertissements, logs, artefacts et événements terminaux, puis refuser toute mutation de résultat ou d'expérience terminale.
- Invariants et garde-fous: aucune réécriture de résultat ou d'expérience; aucun résultat sans hash; aucun artefact sans empreinte; aucune sortie volumineuse sans référence hashée; aucun `FAILED` sans `failure_reason`; aucune métrique sans contexte d'interprétation; aucune chronologie inversée; aucun payload interne du moteur dans le contrat public.
- Dépendances: T-007; `app/contracts/strategy_experiments.py`; DDD-ADR-010.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m011): couvrir resultat experience immuable`
- Commit GREEN: `feat(m011): enregistrer resultat experience immuable`
