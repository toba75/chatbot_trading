# P-002 - Publier la spécification du pipeline local distribué

## Milestone

- Nom : M14-local-pipeline - Pipeline documentaire local distribué.
- Source : `docs/specs/plan_distribution.md`, T-005 à T-008 ; ADR-052.
- Objectif métier : fixer les responsabilités, états et échanges du pipeline à
  la page avant de remplacer l'orchestration locale monoprocessus.

## Contexte DDD

- Domaine : traitement des sources documentaires et accès aux connaissances.
- Bounded contexts : SP possède le traitement, les résultats, la progression
  et la version canonique ; KA possède la projection ; `platform` possède la
  file, les claims, le quota et les enveloppes de complétion.
- Objectif métier : rendre explicite le passage du manifeste figé à une version
  canonique unique puis à une projection locale recherchable.
- Langage ubiquitaire : fan-out, `CONVERT_PAGE`, résultat de page,
  `SKIP_EMPTY`, enveloppe de complétion, assemblage canonique,
  `CanonicalSourcePublished`, `PROJECT_DOCUMENT`, rejeu idempotent.
- Invariants critiques : une transaction forte reste dans un seul propriétaire ;
  le manifeste et son total sont figés ; la progression provient uniquement de
  SP persistant ; la projection ne lit qu'une version canonique publiée.
- Garde-fous : aucune création directe dans `platform.technical_jobs` depuis
  une transaction SP ; aucun worker n'écrit directement un résultat SP ; aucun
  assemblage ne réexécute un modèle ; aucun accès KA direct aux tables internes
  SP ou à un Qdrant d'un autre environnement.

## Blocages Ou Préconditions

- État GREEN/RED connu : P-001 doit avoir fermé les deux RED de prévol et publié
  une gate globale GREEN avant le test RED de cette tâche.
- Présence des milestones amont dans master : M14-distribution-core et ses
  contrats `CONVERT_PAGE`, résultat de page,
  `ASSEMBLE_CANONICAL_DOCUMENT`, quota et outbox de complétion sont présents.
- Décisions manquantes : aucune ADR nouvelle attendue ; la spécification doit
  appliquer ADR-024, ADR-025 et ADR-052. Toute nécessité de transaction forte
  intercontextes ou de seconde file bloque la tâche et impose une ADR remplaçante.
- Risques : confondre job technique et commande métier, rendre un état de worker
  public, ou laisser l'ordre des transactions et acquittements implicite.

## Tâches

### P-002 - Publier la spécification du pipeline local distribué

- But métier : donner un contrat exécutable commun aux quatre tranches T-005 à
  T-008 avant leur premier test d'acceptation.
- Portée DDD : langage ubiquitaire, agrégats propriétaires, commandes, événements,
  ports, états, erreurs stables, ordre des transactions et critères de sortie.
- Scénario BDD :
  - Given un traitement SP possède un manifeste routé figé et deux workers
    documentaires locaux publient la même capacité généraliste.
  - When la spécification distribue les pages, reçoit leurs complétions,
    assemble la version canonique et déclenche sa projection.
  - Then chaque écriture reste chez son propriétaire, chaque échange est
    idempotent et fenced, la publication canonique est unique et KA ne projette
    que cette publication complète dans l'environnement du traitement.
- Tests d'acceptation à écrire : créer le scope `m014_local_pipeline` et un test
  de spécification exigeant mission, contexte DDD, langage, invariants,
  machines d'états, ports, enveloppes, erreurs, scénarios DIST-003 à DIST-005,
  ordre des transactions ADR-024, rollback explicite et exclusions T-009 à
  T-011 ; ajouter sa précondition sans enregistrer encore de test d'implémentation.
- Tests unitaires à écrire : couvrir le validateur de spécification pour
  propriétaire absent, total mutable, transaction intercontexte, progression
  synthétique, assemblage avant complétude, projection avant publication,
  fallback de route et référence d'environnement ambiguë.
- Implémentation attendue : créer
  `docs/specs/m014_local_pipeline_documentaire_distribue.md`, enregistrer le
  validateur sous `ost_gate/`, la précondition sous `gate_tests/preconditions/`
  et le scope dans `gate.toml` ; relier explicitement chaque comportement aux
  fichiers 0003 à 0006 sans modifier le sens d'ADR-052.
- Invariants et garde-fous : la spécification ne crée aucun code de production ;
  elle conserve `CONVERT_DOCUMENT` comme action publique et orchestration de
  compatibilité, mais interdit toute activation implicite du parcours distribué.
- Dépendances : P-001 ; `docs/specs/m004_version_canonique_publiee.md` ;
  `docs/specs/m005_projection_connaissance_recherchable.md` ;
  `docs/specs/m013_environments_environnements_explicites.md` ; ADR-024,
  ADR-025, ADR-052 et DDD-ADR-008.
- Commandes de validation : tests ciblés du validateur de spécification ;
  `uv run --locked gate --scope governance` ;
  `uv run --locked gate --scope m014_local_pipeline` ;
  `uv run --locked gate`.
- Commit RED : `test(m014-pipeline): exiger specification pipeline local distribue`.
- Commit GREEN : `docs(m014-pipeline): publier specification pipeline local distribue`.
