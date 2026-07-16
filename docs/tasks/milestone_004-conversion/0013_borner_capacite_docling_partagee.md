# T-013 - Borner la capacité Docling partagée

## Objectif

Conserver huit pages orchestrées en parallèle sans lancer simultanément plus de
deux processus Docling lourds, standard et Granite confondus.

## Scénario BDD

**Given** un PDF réel dont plusieurs pages utilisent Docling standard, Granite
ou les deux pour l’enrichissement ciblé  
**When** huit pages sont orchestrées simultanément  
**Then** une capacité globale explicite borne à deux tous les processus Docling,
le plafond Granite reste lui-même à deux, les attentes de capacité ne consomment
pas le timeout d’un processus et aucune page native n’échoue par saturation.

## Critères d’acceptation

- `services.workers.concurrency` reste égal à huit.
- `services.workers.docling_concurrency` est obligatoire, strictement positif et
  inférieur ou égal au plafond pagewise.
- Docling standard et Granite partagent la même capacité en mémoire.
- `services.workers.granite_concurrency` reste un plafond Granite distinct et ne
  dépasse ni la capacité Docling ni le plafond pagewise.
- Un test concurrent prouve le maximum combiné.
- Le document réel `DOC-8C536DF8808F9E19` atteint `CANONICAL_ACCEPTED`, puis
  `SEARCHABLE`, sans `DOCLING_STANDARD_UNAVAILABLE`.
- `uv run --locked gate` est GREEN.

## ADR

- ADR-042.
