# ADR-006 - Registre d'affirmations séparé de l'index documentaire

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-006

---

## Contexte

Le système doit distinguer les passages documentaires des propositions structurées qui en sont extraites. Une affirmation doit porter ses preuves, conditions, limites et relations avec d'autres affirmations.

## Décision

L'index vectoriel stocke des fragments documentaires.

Le registre d'affirmations stocke des propositions structurées, leurs preuves, leurs conditions, leurs limites et leurs relations.

Le registre ne remplace pas les passages sources ; il sert de couche d'analyse et d'audit.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Tout stocker dans l'index vectoriel | Rejetée | Mélange preuves et interprétations, rend l'audit difficile. |
| Remplacer les passages par des claims | Rejetée | Perte du lien direct avec la source primaire. |
| Séparer index documentaire et registre d'affirmations | Retenue | Préserve les sources et ajoute une couche analytique auditable. |

## Conséquences

### Positives

- Les synthèses peuvent s'appuyer sur des affirmations vérifiées.
- Les contradictions et dépendances deviennent modélisables.
- L'audit peut distinguer source, déduction et choix de conception.

### Négatives ou coûts

- Nécessite des tables et workflows dédiés.
- L'extraction et la vérification des claims ajoutent de la latence.

### Risques et contrôles

- Risque : claim promu sans support.  
  Contrôle : statut de vérification et liens de preuve obligatoires.

## Impact d'implémentation

- Modules concernés : `app/claims/`, `app/synthesis/`, `app/research/`.
- Configuration concernée : schémas claims, quality gates de vérification.
- Tests attendus : extraction atomique, entailment, rejet des claims sans preuve.
- Milestones concernées : M6, M7, M8.
