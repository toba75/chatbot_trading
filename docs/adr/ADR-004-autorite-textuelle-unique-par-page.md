# ADR-004 - Autorité textuelle unique par page

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, sections 3 et 5

## Contexte

Une même page peut produire du texte natif, une sortie Granite-Docling ou une sortie OCR. Fusionner ces transcriptions sans décision explicite rendrait les preuves impossibles à auditer.

## Décision

Chaque page DOIT avoir une seule autorité textuelle retenue: texte natif, sortie Granite-Docling ou sortie OCR amont explicitement acceptée.

Les sorties concurrentes PEUVENT être conservées comme artefacts d'audit, mais elles NE DOIVENT PAS être fusionnées silencieusement dans la source canonique.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Fusion automatique des transcriptions | Rejetée | Rend les citations et erreurs impossibles à attribuer. |
| Texte natif toujours prioritaire | Rejetée | Certaines couches natives sont défectueuses. |
| Autorité unique par adjudication | Retenue | Préserve traçabilité et décision auditable. |

## Conséquences

### Positives

- Les citations ont une origine textuelle claire.
- Les divergences restent disponibles pour audit.

### Négatives ou coûts

- Une politique d'adjudication est nécessaire.
- Les cas ambigus peuvent bloquer la publication.

### Risques et contrôles

- Risque: page publiée sans autorité. Contrôle: invariant `PAGE_AUTHORITY_MISSING` et tests M-004.

## Impact d'implémentation

- Modules concernés: `source_processing.domain`.
- Configuration concernée: politique de QA documentaire.
- Tests attendus: une page avec sortie native et Granite retient une seule autorité.
- Milestones concernées: M-004.

## Liens de traçabilité

- Spécification: sections 3, 5 et 21.
- Plan d'implémentation: M-004.
- Tests d'acceptation: scénario "une page possède une seule autorité textuelle".
- Commits: à renseigner lors de l'implémentation.
