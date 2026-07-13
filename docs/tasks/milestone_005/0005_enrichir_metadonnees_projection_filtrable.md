# T-005 - Enrichir les métadonnées de projection filtrable

## Milestone
- Nom: M-005 - Projection de connaissance recherchable.
- Source: livrables M-005 enrichissement de métadonnées, filtres vérifiés et recherche avec provenance.
- Objectif métier: permettre une recherche filtrée et diversifiée sans dépendre de détails de stockage.

## Contexte DDD
- Domaine: accès aux connaissances.
- Bounded context: KA.
- Objectif métier: associer aux chunks les métadonnées nécessaires au filtrage, à la diversité et à la fraîcheur de projection.
- Langage ubiquitaire: `SearchFilter`, métadonnées de projection, document, auteur, période, type de contenu, qualité canonique, fraîcheur.
- Invariants critiques: un filtre demandé doit être appliqué explicitement; une projection `STALE` ne doit pas être utilisée silencieusement; les métadonnées ne remplacent jamais la source canonique.
- Garde-fous: pas de filtre ignoré; pas de métadonnée inventée; pas de valeur par défaut pour auteur, date, qualité ou type de chunk.

## Blocages Ou Préconditions
- État GREEN/RED connu: chunks traçables disponibles après T-004.
- Présence des milestones amont dans master: M-004 fournit les signaux de qualité et références canoniques nécessaires.
- Décisions manquantes: aucune si les métadonnées restent dérivées et régénérables.
- Risques: recherche trop large par filtre ignoré; confusion entre qualité documentaire et vérité; diversification impossible faute de métadonnées.

## Tâches
### T-005 - Enrichir les métadonnées de projection filtrable
- But métier: rendre les preuves candidates sélectionnables par mandat de recherche sans exposer Qdrant.
- Portée DDD: objets-valeur de métadonnées, politiques `ProjectionFreshnessPolicy` et `EvidenceDiversificationPolicy`, filtres de recherche et refus explicites.
- Scénario BDD:
  - Given une projection contient des chunks issus de plusieurs documents et auteurs.
  - When une recherche exige un filtre d'auteur, de période ou de type de contenu.
  - Then seuls les chunks satisfaisant explicitement le filtre sont éligibles, avec une trace de filtre consultable.
- Tests d'acceptation à écrire: `uv run --locked gate`, couvrant filtre appliqué, filtre inconnu refusé, projection stale refusée et diversité par document quand elle est demandée.
- Tests unitaires à écrire: tests de `SearchFilter`, `ProjectionMetadata`, `ProjectionFreshnessPolicy`, `EvidenceDiversificationPolicy` et sérialisation de trace.
- Implémentation attendue: enrichir les chunks de métadonnées strictes, construire les filtres KA et refuser toute demande contenant une dimension non supportée.
- Invariants et garde-fous: aucun filtre silencieusement ignoré; aucune recherche sur projection obsolète sans avertissement explicite prévu par le contrat; aucune métadonnée obligatoire vide.
- Dépendances: T-004; ADR-005; DDD-ADR-004; métriques M-005 T-010.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m005): couvrir les filtres de projection`
- Commit GREEN: `feat(m005): enrichir les metadonnees filtrables`
