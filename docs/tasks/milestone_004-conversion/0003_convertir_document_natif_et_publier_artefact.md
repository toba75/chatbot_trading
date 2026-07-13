# T-003 - Convertir un document natif et publier son artefact canonique

## Milestone

- Nom : M04-conversion - Conversion canonique réellement exécutable.
- Source : SP-010 à SP-015 de `docs/specs/m004_version_canonique_publiee.md` et ADR-001 à ADR-004.
- Objectif métier : transformer réellement un document routé `NATIVE_STANDARD` en version canonique traçable.

## Contexte DDD

- Domaine : traitement des sources documentaires.
- Bounded context : SP.
- Objectif métier : produire un `DoclingDocument` unique, un manifeste d'autorité et un artefact JSON canonique immuable.
- Langage ubiquitaire : `ConvertRoutedPages`, `TextAuthorityManifest`, QA pré/post-conversion, `CanonicalSource`, `CanonicalVersionId`.
- Invariants critiques : chaque page du manifeste est convertie une fois, possède une autorité unique, reste dans l'ordre original et pointe vers une provenance résoluble.
- Garde-fous : un PDF ou une sortie Docling incohérente est refusé ; aucun contenu synthétique ne remplace la sortie Docling.

## Blocages Ou Prérequis

- État GREEN/RED connu : T-002 est GREEN.
- Présence des milestones amont dans master : M-003 persiste les routes de pages et M-004 possède les politiques de domaine.
- Décisions manquantes : aucune après ADR-032.
- Risques : une sortie incomplète ne doit jamais être publiée comme canonique.

## Tâches

### T-003 - Convertir un document natif et publier son artefact canonique

- But métier : rendre le chemin Docling standard réellement utile aux PDF natifs routés.
- Portée DDD : adaptateur Docling, worker SP, stockage d'artefacts, persistance de `CanonicalSource` et QA M-004.
- Scénario BDD :
  - Given un PDF natif réel dont toutes les pages sont routées `NATIVE_STANDARD`.
  - When le job `CONVERT_DOCUMENT` est exécuté.
  - Then un Docling JSON haché couvre exactement le manifeste, la version canonique est publiée et chaque page conserve son autorité.
- Tests d'acceptation à écrire : un PDF réel converti par Docling, artefact persistant, statut `CANONICAL_ACCEPTED` et vérification de hash.
- Tests unitaires à écrire : page omise, sortie sans provenance, hash divergent, autorité absente, artefact déjà existant.
- Implémentation attendue : implémenter le port Docling réel, le worker `CONVERT_DOCUMENT`, la persistance transactionnelle des états et le stockage immuable sous `paths.canonical_sources_root`.
- Invariants et garde-fous : le worker ne déclare GREEN qu'après persistance complète ; échec Docling visible et non rejoué comme une autre route.
- Dépendances : T-002.
- Commandes de validation : tests ciblés M04-conversion ; `uv run --locked gate`.
- Commit RED : `test(m04): couvrir conversion native canonique réelle`.
- Commit GREEN : `feat(m04): convertir document natif et publier canonique`.
