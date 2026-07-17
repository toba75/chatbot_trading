# ADR-042 - Capacité Docling partagée

**Statut :** Acceptée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** Pour la capacité des processus Docling, complète et restreint le parallélisme d’ADR-040
**Remplacée par :** Aucune
**Source :** Parcours réel M-004 du document `DOC-8C536DF8808F9E19`

## Contexte

Le runtime orchestre huit pages en parallèle et borne Granite à deux processus.
Docling standard n’est toutefois pas inclus dans cette capacité. Sur un PDF de
265 pages, deux processus Granite et plusieurs processus standard ont saturé le
CPU pendant 58 minutes. Après 159 unités, un processus standard a dépassé son
timeout de 300 secondes et la conversion a terminé avec
`DOCLING_STANDARD_UNAVAILABLE`.

Le plafond Granite d’ADR-040 évite la saturation de Granite par lui-même, mais
ne protège pas le runtime contre la somme des processus standard et Granite.

## Décision

- `services.workers.concurrency` **DOIT** rester le plafond des pages orchestrées.
- `services.workers.docling_concurrency` **DOIT** borner la somme des processus
  Docling standard et Granite d’un worker.
- Docling standard et Granite **DOIVENT** partager la même capacité en mémoire.
- L’attente d’un slot **NE DOIT PAS** démarrer le timeout du sous-processus.
- `services.workers.granite_concurrency` **DOIT** rester un plafond Granite
  distinct et **NE DOIT PAS** dépasser la capacité Docling.
- Les deux capacités **DOIVENT** être strictement positives et ne pas dépasser
  le plafond pagewise.
- La valeur locale explicite de la capacité Docling est deux ; huit pages restent
  orchestrées.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Huit processus standard plus deux Granite | Rejetée | Produit une saturation réelle et un timeout terminal. |
| Réduire le plafond pagewise à deux | Rejetée | Supprime la concurrence des travaux non Docling et contredit l’objectif de huit pages orchestrées. |
| Capacité Docling globale de deux | Retenue | Protège le CPU tout en conservant l’orchestration pagewise et le plafond Granite explicite. |

## Conséquences

### Positives

- Les timeouts mesurent le travail du sous-processus, pas son attente de CPU.
- Les routes natives et enrichies ne se rendent plus mutuellement indisponibles.

### Négatives ou coûts

- Jusqu’à six pages peuvent attendre un slot Docling.
- La configuration gagne une clé obligatoire.

### Risques et contrôles

- Risque de sérialisation excessive : le plafond reste configurable et testé.
- Risque de deux sémaphores indépendants : un test concurrent mesure le maximum
  combiné entre standard et Granite.

## Impact d'implémentation

- Modules concernés : configuration, worker M-004 et limiteur de convertisseurs.
- Configuration concernée : `services.workers.docling_concurrency=2`.
- Tests attendus : capacité combinée, invariants de configuration et parcours réel.
- Milestones concernées : M-004 et M-013 réalité produit.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`.
- Plan d’implémentation : `docs/tasks/milestone_004-conversion/0013_borner_capacite_docling_partagee.md`.
- Tests d’acceptation : `gate_tests/ported/tests/m004/validate_shared_docling_concurrency_unit.py`.
- Commit RED : `10906b600`.
- Commit GREEN : `10ab0ca70`.

## Notes

Acceptée après la conversion réelle complète de `DOC-8C536DF8808F9E19` avec
huit pages orchestrées et deux processus Docling lourds au maximum. Le document
a atteint `SUCCEEDED 265/265`, puis `SEARCHABLE`; la gate verrouillée est GREEN
avec 436 nœuds uniques.
