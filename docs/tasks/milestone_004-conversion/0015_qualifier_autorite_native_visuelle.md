# T-015 - Qualifier l’autorité native d’une page visuelle

## Scénario BDD

**Given** une page complexe composée de graphiques et d’une courte légende native  
**When** le diagnostic mesure la fiabilité de sa couche textuelle  
**Then** la légende est `SUSPECT`, la page suit `SCAN_GRANITE` et aucune autorité
Docling standard inexistante n’est exigée.

## Critères d’acceptation

- Le seuil visuel est nommé, versionné et testé.
- Une page native complexe fiable reste `TARGETED_ENRICHMENT`.
- Les diagnostics pypdf v4 existants sont migrés strictement.
- La page 174 du document réel ne termine plus la conversion.
- Le parcours atteint `CANONICAL_ACCEPTED`, puis `SEARCHABLE`.

## ADR

- ADR-044.
