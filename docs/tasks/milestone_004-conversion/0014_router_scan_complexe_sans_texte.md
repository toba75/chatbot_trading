# T-014 - Router un scan complexe sans texte natif

## Scénario BDD

**Given** une page avec texte natif absent, scan propre et mise en page complexe  
**When** le diagnostic et le routage sont exécutés  
**Then** la page est `SCAN_CLEAN`, suit `SCAN_GRANITE` et n’exige aucun candidat
Docling standard inexistant.

## Critères d’acceptation

- Le cas exact est couvert par un test automatisé.
- Les décisions persistées selon l’ancienne priorité sont migrées.
- La page 166 du document `DOC-8C536DF8808F9E19` ne termine plus la conversion.
- Le parcours atteint `CANONICAL_ACCEPTED`, puis `SEARCHABLE`.

## ADR

- ADR-043.
