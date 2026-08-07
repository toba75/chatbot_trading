# Contrat des chunks de l'index RAG — schéma version 1

Ce contrat est produit par `qualification/corpus_reference/chunks.py` (export :
`uv run python -m qualification.corpus_reference.chunks export`). Les fichiers
`chunks.jsonl` résident dans les répertoires de travail par livre, jamais dans
le dépôt : ils contiennent le texte d'ouvrages sous droit d'auteur.

## Forme

Un fichier par livre, en JSON Lines. La première ligne est un en-tête :

```json
{"type": "header", "schema_version": 1,
 "contract": {"analyzer_version": "…", "capability_profile": "…"},
 "document": {"name": "…", "sha256": "…"}, "chunks": N,
 "unlocatable_items": ["#/texts/1062", "…"]}
```

`unlocatable_items` consigne les items du corps écartés faute de toute
localisation (artefacts de conversion) : rien ne disparaît en silence.

Chaque ligne suivante est un chunk :

```json
{"type": "chunk", "chunk_id": "<sha256:12>:<index:05d>",
 "text": "…items joints par \n…",
 "provenance": {"page": 9, "bbox": [l, t, r, b]},
 "source": {"source_sha256": "…", "document_kind": "book",
             "source_catalog_schema_version": 1,
             "source_catalog_entry_sha256": "…", "…": "projection stable"},
 "items": [{"docling_ref": "#/texts/68", "label": "text", "charspan": [a, b]}],
 "formulas": [{"kind": "inline|display", "charspan": [a, b],
               "docling_ref": "#/texts/68", "item_charspan": [a, b],
               "flag": "proven|corroborated|unverified|contradicted",
               "evidence": {"conformant": n, "contradicted": n, "other": n,
                             "coverage": r},
               "provenance": {"page": 9, "bbox": [l, t, r, b],
                               "precision": "region|item|chunk"}}]}
```

Toutes les boîtes sont en points PDF, origine **TOPLEFT**, directement
utilisables pour produire un crop de citation (`fitz.Rect` sur la page
indiquée) — vérifié visuellement sur les trois drapeaux émis. La `precision`
déclare la source de la boîte : une région Docling n'est retenue que si son
span **contient** la formule (un chevauchement partiel citerait de la prose) ;
à défaut la boîte de l'item, à défaut celle du chunk.

## Projection du registre de sources

Quand `--catalog docs/source_catalog/catalog.json` est fourni, chaque chunk
porte une projection reconstruite depuis le registre et l'entrée du manifeste.
Elle conserve `source_sha256`, le type de publication, l'identité bibliographique
éventuellement prouvée avec ses références de provenance, les trois dates
distinctes, l'état de résolution et la revue éditoriale datée.
`source_catalog_entry_sha256` permet de retrouver la version exacte de l'entrée
utilisée.

Les observations commerciales brutes, les rangs et les notes ne sont pas dans
la projection : ils restent séparés pour les évaluations d'ablation futures.
Ils ne modifient ni le texte dense ni le drapeau de preuve. Une projection sans
registre vérifié est refusée par la commande d'export du corpus réel.

## Découpage

Un chunk est une suite d'items Docling de la couche BODY (texte, listes,
titres, légendes, notes, code, formules), joints par des sauts de ligne,
rompue : au changement de page, à chaque titre de section, et au-delà de
1 800 caractères sans jamais scinder un item. Les charspans des items et des
formules sont exprimés dans le texte du chunk ; `item_charspan` donne le même
span dans le texte de l'item d'origine, ce qui relie chaque formule au
`DoclingDocument` natif, qui reste l'autorité.

Les formules sont énumérées par les mêmes autorités que le pipeline de
qualification : les items `formula` entiers (`kind: display`) et les spans
`$…$` de `pdf_math_audit.inline_math` (`kind: inline`) — les blocs de code et
les couches hors corps n'en produisent jamais.

## Sémantique des drapeaux

Le drapeau d'une formule dérive du champ `verdict` des régions sources
**liées** du rapport dont le `candidate_charspan` chevauche la formule — le
verdict du pipeline est la seule autorité :

- `contradicted` : au moins une région chevauchante porte le verdict
  `contradicted` — y compris les régions `missing`, dont la transcription a
  perdu des jetons prouvés. La contradiction domine tout.
- `proven` : au moins une région `conformant_within_scope`, aucune
  contradiction, et les régions conformes couvrent **l'intégralité** des
  caractères effectifs de la formule (tout sauf espaces et `$`). Cette règle
  n'est pas un seuil choisi : sur les 37 livres exportés, 93 formules portent
  des preuves conformes sans contradiction — 23 à couverture exactement 1,0,
  aucune entre 0,55 et 1,0, 70 en dessous. Une couverture partielle reste
  `unverified`, le détail (`evidence.coverage`) étant conservé.
- `corroborated` : réservé à l'accord d'un second modèle indépendant mesuré par
  l'étape 6 du plan 004. **Jamais émis par cet exporteur** ; aucun drapeau ne
  surclasse la preuve.
- `unverified` : tout le reste — y compris les formules des livres dont les
  polices bloquent la preuve, qui restent dans l'index avec leur incertitude
  explicite.

## Validation

`validate_chunk` refuse tout chunk dont une formule n'a pas un drapeau de
l'énumération ou n'a pas de provenance complète (page et boîte) ; l'export
échoue alors explicitement. Le contre-exemple est un test
(`test_refuse_une_formule_sans_drapeau_ou_sans_provenance`).

## Évolution

Tout changement de forme ou de sémantique incrémente `schema_version` et se
documente ici. Les consommateurs refusent une version qu'ils ne connaissent
pas.
