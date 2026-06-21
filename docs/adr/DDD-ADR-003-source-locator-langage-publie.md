# DDD-ADR-003 - SourceLocator comme langage publié

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 4

## Contexte

Les contextes aval doivent citer des preuves sans lire les structures internes du traitement documentaire. La traçabilité exige un contrat stable jusqu'à la page et au fragment.

## Décision

`SourceLocator` est le langage publié pour référencer une preuve documentaire. Il doit contenir la version canonique, le document, la page PDF, l'item source et le hash de contenu.

Un localisateur ne peut pas pointer vers une version en quarantaine ou retirée sans avertissement explicite.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Chemin de fichier comme référence | Rejetée | Instable et insuffisant pour la citation fine. |
| Identifiant Qdrant comme référence | Rejetée | Projection régénérable, pas source de vérité. |
| `SourceLocator` publié | Retenue | Contrat stable intercontexte. |

## Conséquences

### Positives

- Les citations sont résolvables sans couplage aux tables SP.
- Les incohérences de contenu peuvent être détectées.

### Négatives ou coûts

- Les contrats doivent rester compatibles en lecture.

### Risques et contrôles

- Risque: localisateur obsolète après correction. Contrôle: versions immuables et supersession explicite.

## Impact d'implémentation

- Modules concernés: SP, KA, EG, RA, CV.
- Configuration concernée: schémas de contrats.
- Tests attendus: sérialisation, désérialisation, résolvabilité et refus de version invalide.
- Milestones concernées: M-001, M-004, M-005.

## Liens de traçabilité

- Spécification: sections 3, 4, 5, 6 et 21.
- Plan d'implémentation: M-001.
- Tests d'acceptation: recherche traçable et citation ouvrable.
- Commits: à renseigner lors de l'implémentation.
