# ADR-044 - Autorité native d’une page visuelle complexe

**Statut :** Proposée
**Date :** 2026-07-16
**Décideurs :** Équipe OSTrading
**Remplace :** Pour une page visuelle complexe à texte natif parcellaire, la priorité `COMPLEX_VISUAL` d’ADR-033 et l’obligation de candidat natif d’ADR-040
**Remplacée par :** Aucune
**Source :** Page 174 du document réel `DOC-8C536DF8808F9E19`

## Contexte

La page 174 contient deux graphiques et une seule chaîne native de 41
caractères correspondant à leur légende. L’inspecteur la qualifie pourtant de
texte natif `RELIABLE` dès 20 caractères. `COMPLEX_VISUAL` impose alors
`TARGETED_ENRICHMENT`, dont le candidat Docling standard est obligatoire.
Docling ne trouve aucune provenance sur cette page et termine avec
`DOCLING_STANDARD_UNAVAILABLE`, alors que l’autorité utile est visuelle.

Les autres pages ciblées du même document ont été vérifiées isolément : Docling
standard réussit. Le défaut n’est donc ni une indisponibilité générale de
Docling ni une raison d’autoriser un fallback après n’importe quel échec.

## Décision

- Sur une page comportant des images et une mise en page complexe, une couche
  native de moins de 80 caractères **DOIT** être qualifiée `SUSPECT`, même si
  son ratio alphanumérique dépasse le seuil général.
- Une page `COMPLEX`, `SCAN_CLEAN` et dont le texte natif est `ABSENT` ou
  `SUSPECT` **DOIT** être classée `SCAN_CLEAN` puis suivre `SCAN_GRANITE`.
- Une page complexe dont le texte natif est `RELIABLE` **DOIT** conserver
  `COMPLEX_VISUAL`, `TARGETED_ENRICHMENT` et l’adjudication ADR-040.
- La récupération Gemma après échec Granite reste explicite, page par page et
  tracée selon son contrat existant. Aucun échec Docling standard générique ne
  déclenche une nouvelle route au runtime.
- Les diagnostics pypdf v4 déjà persistés avec le format de justification
  canonique **DOIVENT** être migrés selon les mêmes signaux et le même seuil.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Autoriser Granite après tout échec Docling ciblé | Rejetée | Masquerait une panne réelle du candidat natif obligatoire. |
| Router seulement la page 174 par identifiant | Rejetée | Corrigerait une donnée sans corriger la règle qui l’a produite. |
| Distinguer légende parcellaire et autorité native fiable | Retenue | Corrige le diagnostic avant exécution et conserve ADR-040 pour les vraies pages natives complexes. |

## Conséquences

### Positives

- Une courte légende ne force plus un candidat natif inexistant.
- Les graphiques restent traités par Granite, puis éventuellement Gemma de
  manière explicite pour la seule page en échec.

### Négatives ou coûts

- Le seuil de 80 caractères devient une règle versionnée du diagnostic pypdf.
- Une migration recalcule les plans de route déjà persistés concernés.

### Risques et contrôles

- Risque de dérouter une vraie page native : le seuil ne s’applique qu’aux
  pages avec images et mise en page complexe ; un test conserve explicitement
  `TARGETED_ENRICHMENT` lorsque le texte est fiable.

## Impact d'implémentation

- Modules concernés : inspecteur pypdf, politique de diagnostic et migration PostgreSQL.
- Configuration concernée : aucune valeur implicite.
- Tests attendus : légende parcellaire visuelle et page native complexe fiable.
- Milestones concernées : M-003, M-004 et M-013 réalité produit.

## Liens de traçabilité

- Spécifications : `docs/specs/m003_source_enregistree_diagnostiquee_routee.md` et `docs/specs/m004_version_canonique_publiee.md`.
- Plan d’implémentation : `docs/tasks/milestone_004-conversion/0015_qualifier_autorite_native_visuelle.md`.
- Test d’acceptation : `gate_tests/ported/tests/m003/validate_sparse_visual_native_text_unit.py`.
- Commits : à compléter.

## Notes

L’ADR reste proposée jusqu’au parcours réel complet et à la gate canonique.
