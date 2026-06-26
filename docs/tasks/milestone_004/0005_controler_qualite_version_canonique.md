# T-005 - Contrôler la qualité de la version canonique

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1, sections qualité documentaire et critères V1.
- Objectif métier: sélectionner les pages critiques avant conversion et refuser une version canonique lorsque la structure, les chiffres, signes, tableaux ou pages ne satisfont pas la politique d'acceptation canonique.

## Contexte DDD
- Domaine: qualité documentaire avant publication.
- Bounded context: `SP`.
- Objectif métier: décider les pages critiques et comparaisons de routes avant conversion, puis transformer les sorties adjugées en candidat canonique publiable seulement si les contrôles qualité requis sont satisfaits.
- Langage ubiquitaire: contrôle qualité pré-conversion, `CriticalPageSamplingPolicy`, comparaison de routes, `PASS`, `PASS_WITH_WARNINGS`, `RETRY_WITH_ALTERNATIVE_ROUTE`, `MANUAL_REVIEW`, `QUARANTINE`, contrôle qualité post-conversion, page omise, cohérence numérique, signes, tableaux, `CanonicalAcceptancePolicy`, refus de publication.
- Invariants critiques: les pages critiques sont sélectionnées explicitement; un retry de route est une décision métier tracée et non un fallback silencieux; aucune page omise; tout échec de QA bloque la publication; les anomalies numériques ou de tableau sont explicites; la politique de QA est versionnée.
- Garde-fous: pas de seuil implicite; pas de validation de surface sur JSON seulement; pas de correction automatique non tracée; pas de changement de route sans statut `RETRY_WITH_ALTERNATIVE_ROUTE`.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 à T-004 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: une ADR est requise si la politique de QA change l'autorité canonique; les seuils expérimentaux fins restent calibrés en M-012 et ne doivent pas être figés sans mesure.
- Risques: laisser une version fausse mais bien formée; publier un tableau incomplet; considérer un test logiciel GREEN comme preuve scientifique de fidélité documentaire; réessayer une route comme fallback au lieu d'enregistrer une décision `RETRY_WITH_ALTERNATIVE_ROUTE`.

## Tâches
### T-005 - Contrôler la qualité de la version canonique
- But métier: empêcher la publication d'une version canonique qui perd des pages ou altère des informations critiques.
- Portée DDD: politiques normatives `CriticalPageSamplingPolicy` et `CanonicalAcceptancePolicy`, rapport QA pré et post-conversion, erreurs métier de publication, métriques minimales de conversion et conservation des anomalies.
- Scénario BDD:
  - Given une source routée contient une page à faible confiance et une table financière dont une conversion perd un signe négatif.
  - When le contrôle qualité pré-conversion puis post-conversion M-004 est exécuté.
  - Then la page critique est sélectionnée explicitement, le retry de route éventuel est tracé comme `RETRY_WITH_ALTERNATIVE_ROUTE`, la version canonique candidate est refusée avec anomalie explicite et aucun événement de publication n'est produit.
- Tests d'acceptation à écrire: un test `tests/m004/validate_canonical_quality_acceptance.ps1` couvrant échantillonnage critique pré-conversion, comparaison de routes, statut `RETRY_WITH_ALTERNATIVE_ROUTE`, page omise, incohérence numérique, signe altéré, tableau incomplet et source quarantinée non publiable.
- Tests unitaires à écrire: tests de `CriticalPageSamplingPolicy`, `CanonicalAcceptancePolicy`, complétude pages, politique de seuils versionnée, refus QA sans rapport, blocage de publication, conservation des anomalies, statuts `PASS`, `PASS_WITH_WARNINGS`, `MANUAL_REVIEW`, `QUARANTINE` et absence de correction silencieuse.
- Implémentation attendue: créer le rapport QA M-004 pré et post-conversion, les règles minimales de cohérence documentaire, les statuts de décision explicites, les erreurs explicites et les métriques auditables sans contenu intégral de document.
- Invariants et garde-fous: rapport QA pré-conversion obligatoire; rapport QA post-conversion obligatoire; statut de publication interdit si QA RED; aucune page absente; aucune métrique calculée par LLM; aucun contenu documentaire complet dans les logs; aucun retry sans décision métier enregistrée.
- Dépendances: T-004; ADR-001; ADR-004; critères M-012 futurs pour calibration élargie.
- Commandes de validation: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_quality_acceptance.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\tests\m004\validate_canonical_quality_unit.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\test.ps1`; `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\lint.ps1`.
- Commit RED: `test(m004): couvrir le controle qualite canonique`.
- Commit GREEN: `feat(m004): controler la qualite de version canonique`.
