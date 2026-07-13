# T-006 - Accepter les décisions de conversion effectivement livrées

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : ADR-032, ADR-033, `docs/tasks/milestone_004-conversion/journal.md`
  et `docs/reports/m04_conversion_non_native_proof.md`.
- Objectif métier : faire correspondre le statut normatif des décisions à la
  chaîne réellement livrée et prouvée, sans transformer rétrospectivement une
  preuve partielle en réussite.

## Contexte DDD

- Domaine : gouvernance de livraison du traitement des sources.
- Bounded context : gouvernance transverse ; les décisions concernent SP et
  platform, sans modifier leurs responsabilités.
- Objectif métier : rendre normatif l'usage des runtimes réels de conversion et
  la priorité des signaux OCR une fois leurs preuves produites.
- Langage ubiquitaire : ADR proposée, ADR acceptée, preuve réelle, bascule
  atomique, allowlist historique.
- Invariants critiques : une ADR ne devient `Acceptée` qu'après adaptateurs,
  actifs, routes, progression publique et preuve réelle ; l'index ADR, les
  tests de gouvernance et les empreintes historiques décrivent le même état.
- Garde-fous : l'échec OCR vers Granite observé reste une erreur terminale
  publique et ne devient pas une conversion réussie ; aucun statut ne masque
  cette limite.

## Blocages Ou Prérequis

- État GREEN/RED connu : `uv run --locked gate` a validé 406 nœuds uniques
  après T-005 ; `uv sync --locked`, `uv lock --check` et `git diff --check`
  sont GREEN.
- Présence des milestones amont dans master : M-003 publie les routes et M-004
  possède désormais les adaptateurs réels sur la branche de conversion.
- Décisions manquantes : aucune ; T-006 accepte ADR-032 et ADR-033, sans les
  modifier ni remplacer.
- Risques : un test qui exige encore `Proposée`, un index incohérent ou une
  empreinte historique non réconciliée rendrait la gouvernance RED.

## Tâches

### T-006 - Accepter les décisions de conversion effectivement livrées

- But métier : clôturer normativement la décision d'exécution réelle et la
  priorité OCR après leurs preuves de production locale.
- Portée DDD : ADR, index, tests de gouvernance, allowlist historique et
  journal ; aucune transition métier nouvelle.
- Scénario BDD :
  - Given ADR-032 et ADR-033 sont proposées, que leurs adaptateurs, actifs,
    preuves UI et erreurs terminales publiques sont documentés.
  - When la gouvernance valide la clôture de M04-conversion.
  - Then les deux ADR et leur index deviennent `Acceptée`, leurs contrats de
    test le vérifient et l'allowlist historique reste fermée et intègre.
- Tests d'acceptation à écrire : contrôle de gouvernance exigeant le statut
  `Acceptée` d'ADR-032 et ADR-033 ainsi que leurs entrées d'index cohérentes.
- Tests unitaires à écrire : contrôle de l'allowlist historique prouvant que
  tout contenu d'ADR hors empreinte attendue reste RED.
- Implémentation attendue : accepter les deux ADR, mettre à jour l'index, les
  liens de traçabilité, les empreintes strictement nécessaires et le journal.
- Invariants et garde-fous : ne pas modifier le sens des décisions ; ne pas
  présenter l'échec OCR observé comme un succès ; n'ajouter aucun chemin à
  l'allowlist historique.
- Dépendances : T-005.
- Commandes de validation : tests de gouvernance ciblés ; `uv run --locked
  gate` ; `git diff --check`.
- Commit RED : `test(gouvernance): exiger ADR conversion acceptées`.
- Commit GREEN : `docs(m04): accepter décisions conversion livrées`.
