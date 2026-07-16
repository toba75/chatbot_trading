# T-012 - Ignorer les pages vides et résoudre la revue manuelle

## Objectif

Permettre à un document contenant une page diagnostiquée `EMPTY` de poursuivre
sa conversion sans appel d'outil, et rendre toute véritable `MANUAL_REVIEW`
actionnable depuis l'UI jusqu'à la persistance publique.

## Scénarios BDD

### Page vide ignorée

**Given** un PDF diagnostiqué page par page dont la page 2 est `EMPTY`  
**When** le routage puis la conversion canonique sont exécutés  
**Then** la page 2 reçoit `SKIP_EMPTY`, aucun convertisseur ne la reçoit, les
autres pages conservent leur numéro PDF et la progression atteint le total.

### Revue manuelle résolue

**Given** un document en `MANUAL_REVIEW` pour une page non vide sans route  
**When** un réviseur confirme la page vide ou lui assigne une route explicite  
**Then** la décision, le réviseur et le motif sont persistés et le document passe
à `ROUTE_PLANNED` dès que toutes les pages bloquantes sont résolues.

### Document rejeté

**Given** un document en `MANUAL_REVIEW`  
**When** le réviseur choisit `REJECT_DOCUMENT` avec un motif  
**Then** le document passe à l'état terminal `REJECTED` et aucune conversion ne
devient disponible.

## Critères d'acceptation

- `EMPTY` ne produit plus `MANUAL_REVIEW`.
- `SKIP_EMPTY` ne déclenche aucun outil de conversion.
- L'API de revue refuse les décisions incomplètes ou incohérentes.
- L'UI affiche `Examiner` et les trois décisions réelles.
- Les décisions survivent à une relecture PostgreSQL.
- Un parcours réel ajout → diagnostic → revue éventuelle → conversion →
  projection ne présente aucune erreur.
- `uv run --locked gate` est GREEN.

## ADR

- ADR-041.
