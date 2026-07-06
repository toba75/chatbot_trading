# Rapport de benchmark recherche KA M-012

## Scénario BDD

- Given un jeu de 100 à 300 questions annotées avec pages attendues.
- When la recherche de connaissances est exécutée sur une projection KA versionnée et recherchable.
- Then Recall@5, Recall@10, Recall@20, MRR, nDCG, exactitude de page, diversité documentaire, couverture des sous-thèmes et performance FR vers source EN sont publiés sans retirer les questions échouées.

## Contrat publié

- Le jeu `SearchEvaluationSet` refuse moins de 100 questions, plus de 300 questions et toute question sans page attendue.
- Les candidats `KnowledgeSearchCandidate` sont comptés seulement s'ils portent un `SourceLocator` résoluble, un hash de contenu et la version de projection.
- `KnowledgeProjectionSnapshot` bloque la promotion si la projection est obsolète ou sans version.
- Les métriques sont publiées avec un dénominateur explicite.

## Métriques normatives

- `knowledge_recall_at_5`
- `knowledge_recall_at_10`
- `knowledge_recall_at_20`
- `knowledge_mrr`
- `knowledge_ndcg`
- `knowledge_expected_page_accuracy`
- `knowledge_document_diversity`
- `knowledge_subtheme_coverage`
- `knowledge_fr_to_en_recall_at_10`

ADR: non requise; T-007 applique ADR-005, ADR-010 et DDD-ADR-004 sans modifier leur sens.
