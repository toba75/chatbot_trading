# ADR-007 - Déploiement local sur DGX Spark

**Statut :** Acceptée  
**Date :** 2026-06-20  
**Décideurs :** Projet chatbot trading  
**Remplace :** Aucun  
**Remplacée par :** Aucune  
**Source :** `docs/specification_pipeline_chatbot_trading_dgx_spark_v3_1.md`, section 3, ADR-007

---

## Contexte

Le produit cible est un chatbot personnel local-first exécuté sur NVIDIA DGX Spark. Le corpus est privé et les services internes manipulent des documents, embeddings, historiques de conversation et résultats de backtests.

## Décision

Le déploiement cible est local sur DGX Spark.

Les services DOIVENT être liés à l'interface locale, sauf décision explicite d'accès depuis un réseau privé contrôlé.

Par défaut, les services internes écoutent sur `127.0.0.1`.

## Options considérées

| Option | Décision | Raisons |
|---|---|---|
| Déploiement cloud par défaut | Rejetée | Incompatible avec le périmètre local-first et la confidentialité du corpus. |
| Exposition réseau large par défaut | Rejetée | Augmente inutilement la surface d'attaque. |
| Déploiement local avec ports liés à `127.0.0.1` | Retenue | Cohérent avec l'usage personnel et la sécurité attendue. |

## Conséquences

### Positives

- Confidentialité renforcée.
- Contrôle local des modèles, index et documents.
- Réduction de la dépendance aux services distants.

### Négatives ou coûts

- L'utilisateur doit gérer ressources, stockage, sauvegardes et mises à jour locales.
- Les profils de charge doivent éviter les pics mémoire inutiles.

### Risques et contrôles

- Risque : exposition accidentelle d'un port interne.  
  Contrôle : tests de configuration, bind `127.0.0.1`, revue sécurité.

## Impact d'implémentation

- Modules concernés : `app/api/`, `app/orchestration/`, `ui/`, workers.
- Configuration concernée : `config/security.yaml`, `docker-compose.yml`, `config/models.yaml`.
- Tests attendus : ports locaux, absence d'exposition publique, readiness des services.
- Milestones concernées : M1, M5, M9.
