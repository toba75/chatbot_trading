# ADR-035 - Récupération Gemma explicite après provenance Granite absente

**Statut :** Acceptée
**Date :** 2026-07-14
**Décideurs :** Équipe OSTrading
**Remplace :** ADR-032
**Remplacée par :** ADR-040 pour `TARGETED_ENRICHMENT` seulement
**Source :** Demande utilisateur du 2026-07-14 ;
`docs/specs/m004_version_canonique_publiee.md` ; ADR-014, ADR-015, ADR-031,
ADR-032 et ADR-034.

## Contexte

Granite-Docling est l'outil premier des routes M-003 non natives. La première
page de `Trading on Momentum` a cependant produit une page graphique sans
provenance textuelle exploitable : l'échec était alors réduit à
`GRANITE_DOCLING_UNAVAILABLE`, sans pouvoir distinguer une indisponibilité du
runtime d'une page effectivement analysée mais sans texte structurée.

ADR-034 a rendu le transit d'une image vers Gemma 4 possible par le seul
`llm-gateway`. Elle ne faisait pas de Gemma une autorité documentaire. Cette
décision change explicitement cette dernière limite, tout en conservant les
invariants d'artefact canonique, d'autorité textuelle unique, d'isolation et
de progression publique d'ADR-032.

## Décision

- ADR-032 est remplacée : toutes ses obligations restent applicables, sauf son
  interdiction absolue de récupération après Granite.
- `GRANITE_DOCLING` reste le premier et unique essai normal pour
  `SCAN_GRANITE`, `BAD_OCR_TO_GRANITE`, `MIXED_PAGEWISE`,
  `TARGETED_ENRICHMENT` et `PREPROCESS_GRANITE` après OCRmyPDF.
- Gemma 4 **DOIT** être appelée une seule fois et seulement lorsque Granite a
  réellement terminé la page avec `DOCLING_PROVENANCE_MISSING`. Une absence
  d'actif, un timeout, une indisponibilité Granite, un hash divergent ou tout
  autre code **NE DOIT PAS** déclencher Gemma.
- Le rendu de page et l'appel Gemma **DOIVENT** s'exécuter dans un processus
  isolé. Ce processus **DOIT** appeler exclusivement
  `llm-gateway/v1/infer`; il **NE DOIT PAS** joindre Spark, vLLM ou un modèle
  par une autre adresse.
- Gemma **DOIT** être le modèle configuré `google/gemma-4-26B-A4B-it`. Sa
  réponse structurée doit contenir au moins un bloc textuel et, pour chaque
  bloc, une bbox normalisée de 0 à 1000. Une sortie sans texte, sans
  coordonnées, hors limites ou de modèle différent est terminale et publique.
- La sortie Gemma admissible devient l'autorité textuelle unique de cette page
  seulement. L'artefact canonique **DOIT** conserver le nom et la version de
  l'outil, la référence d'audit et la trace
  `GRANITE_DOCLING/DOCLING_PROVENANCE_MISSING`. Il ne doit pas fusionner une
  sortie Granite vide avec Gemma.
- Pendant le travail, le worker **DOIT** persister `RUNNING` et le nombre de
  pages effectivement terminées après chaque page. Le contrat public et l'UI
  lisent exclusivement ces unités persistées. L'appel Gemma en cours reste
  `RUNNING`; il ne peut ni être présenté comme une réussite ni masquer son
  échec terminal.
- Les nouveaux codes terminaux stables incluent
  `GEMMA_VISION_UNAVAILABLE`, `GEMMA_VISION_OUTPUT_INVALID`,
  `GEMMA_VISION_MODEL_MISMATCH`, `GEMMA_VISION_RENDERING_FAILED` et
  `GEMMA_VISION_IMAGE_TOO_LARGE`. Aucun autre modèle, OCR, retry documentaire
  ou chemin synthétique ne leur succède.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Granite puis Gemma 4 sur `DOCLING_PROVENANCE_MISSING` strict | Retenue | Récupère une page réellement analysée mais dépourvue de provenance, avec une trace canonique et contrôlée. |
| Gemma après tout échec Granite | Rejetée | Masquerait l'indisponibilité des actifs ou du runtime et créerait un fallback silencieux. |
| Appel direct Spark/vLLM | Rejetée | Viole ADR-014, ADR-015 et ADR-034. |
| Conserver le texte OCR comme résultat alternatif | Rejetée | OCRmyPDF est un prétraitement, pas une autorité documentaire de remplacement. |

## Conséquences

### Positives

- Les pages graphiques lisibles par Gemma ne bloquent plus automatiquement la
  conversion si Granite a explicitement signalé l'absence de provenance.
- La version canonique porte l'outil ayant réellement produit chaque page et
  la cause Granite ayant autorisé la récupération.
- Le pourcentage UI progresse par page réellement convertie, sans compteur
  synthétique.

### Négatives ou coûts

- Une page récupérée entraîne un rendu PNG local et une inférence Gemma 4.
- La qualité Gemma doit continuer d'être contrôlée par la QA M-004 avant toute
  publication canonique.

### Risques et contrôles

- Risque : accepter Gemma comme solution générale. Contrôle : un seul code
  déclencheur, un seul essai et une trace obligatoire.
- Risque : géométrie inventée. Contrôle : schéma JSON strict et validation des
  coordonnées avant fusion.
- Risque : perte de l'échec Granite. Contrôle : trace immuable dans chaque
  page canonique récupérée.

## Impact d'implémentation

- Modules concernés : ports de conversion SP, adapter Granite, adapter Gemma
  Vision isolé, contrat `llm-gateway`, persistance de progression et migration
  PostgreSQL.
- Configuration concernée : `pypdfium2==5.11.0` est une dépendance directe
  verrouillée pour le rendu PNG; le modèle Gemma reste déclaré par la
  configuration applicative existante.
- Tests attendus : déclencheur Granite unique, absence de récupération sur
  indisponibilité, trace canonique, contrat image, modèle/provenance, schéma et
  progression persistée.
- Milestones concernées : M-002, M04-conversion et M-013.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0007_recuperer_gemma_apres_provenance_granite_absente.md`.
- Tests d'acceptation et unitaires :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Commits : RED `488ec2b82`; GREEN à renseigner après validation.

## Notes

La preuve réelle de conception a utilisé la première page de
`data/corpus/DOC-6A77FD40209CBB1E/...pdf` : Gemma 4 a retourné les six blocs
du titre et leurs coordonnées par `llm-gateway`. Cette preuve ne remplace pas
la QA post-conversion ni la gate canonique.
