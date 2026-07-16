# ADR-036 - Récupération Gemma explicite après échec terminal Granite

**Statut :** Proposée
**Date :** 2026-07-14
**Décideurs :** Équipe OSTrading
**Remplace :** ADR-035
**Remplacée par :** ADR-040 pour `TARGETED_ENRICHMENT` seulement
**Source :** Parcours réel demandé par l’utilisateur le 2026-07-14 ;
`docs/specs/m004_version_canonique_publiee.md` ; ADR-014, ADR-015, ADR-031,
ADR-034 et ADR-035.

## Contexte

Le parcours réel de `Trading on Momentum` a enregistré, diagnostiqué et routé
289 pages. Granite-Docling a traité la première page non native, les quatre
premières pages ont été terminées, puis la page 5
`TARGETED_ENRICHMENT` a échoué avec `GRANITE_DOCLING_UNAVAILABLE`.

ADR-035 ne permettait Gemma 4 qu'après `DOCLING_PROVENANCE_MISSING`. Or ce
code terminal est produit après une tentative réelle du sous-processus Granite
et ne doit pas rendre la conversion utilisateur définitivement impossible
lorsque Gemma est disponible par le chemin autorisé. Le refus actuel ne
protège donc pas l'invariant métier : produire une autorité textuelle unique
pour chaque page routée, ou publier un échec explicite de l'outil qui a aussi
été tenté.

## Décision

- ADR-035 est remplacée. Granite-Docling demeure le premier essai, unique et
  obligatoire de chaque route non native M-003.
- Après cet essai réel, Gemma 4 **DOIT** recevoir un premier rendu non tourné
  pour `DOCLING_PROVENANCE_MISSING` ou `GRANITE_DOCLING_UNAVAILABLE`.
- Si, et seulement si, cette première réponse Gemma est refusée pour
  `GEMMA_VISION_OUTPUT_INVALID`, le worker **DOIT** effectuer un second et
  dernier appel Gemma avec le rendu tourné de 90 degrés. Les coordonnées de ce
  rendu sont réexprimées dans le repère PDF initial et la version d'outil porte
  explicitement `render-rotation-090`.
- Un refus `LLM_RESPONSE_INVALID_JSON` ou `LLM_RESPONSE_SCHEMA_INVALID` du
  gateway **DOIT** devenir `GEMMA_VISION_OUTPUT_INVALID`; il prouve que Gemma a
  répondu avec une sortie contractuellement invalide et ne doit jamais être
  publié comme une indisponibilité du service.
- Le budget Gemma de conversion d'une page **DOIT** être de 4 096 jetons. Le
  délai de supervision du client local **DOIT** couvrir toutes les tentatives
  avant premier token configurées par le gateway, plus 30 secondes explicites
  pour le rendu, le transport local et la validation. Le sous-processus ne doit
  jamais interrompre le retry que le gateway est encore en train de superviser.
- Cette récupération **DOIT** passer exclusivement par
  `llm-gateway/v1/infer`, avec le modèle configuré
  `google/gemma-4-26B-A4B-it`; aucun appel direct à Spark, vLLM ou un autre
  modèle n'est autorisé.
- La sortie Gemma admissible **DOIT** contenir du texte et des coordonnées
  normalisées. Elle devient l'unique autorité textuelle de la page et porte
  obligatoirement la trace Granite exacte, y compris
  `GRANITE_DOCLING_UNAVAILABLE` lorsqu'elle en est issue.
- Une erreur d'actif, d'OCRmyPDF, de source, de contrat, de stockage ou Gemma
  elle-même, hors `GEMMA_VISION_OUTPUT_INVALID` du premier rendu non tourné,
  **NE DOIT PAS** déclencher un autre essai. Elle reste terminale et publique.
- Le worker **DOIT** persister `RUNNING`, les unités réellement terminées, puis
  `CANONICAL_ACCEPTED` ou l'erreur terminale. L'UI lit uniquement cet état
  public persistant.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Granite puis Gemma après un code terminal explicitement autorisé | Retenue | Le parcours reste traçable et peut achever la conversion réelle. |
| Arrêter le document au premier `GRANITE_DOCLING_UNAVAILABLE` | Rejetée | Le code survient après un essai Granite réel et bloque inutilement une page récupérable. |
| Retry Granite implicite | Rejetée | Masquerait l'état de l'outil et allongerait la conversion sans décision explicite. |
| Appel direct de Gemma sur Spark ou vLLM | Rejetée | Viole ADR-014, ADR-015 et ADR-034. |

## Conséquences

### Positives

- Une page non native dont Granite échoue réellement peut être convertie par
  Gemma avec une provenance canonique complète.
- Le parcours UI reste un flux unique : API, outbox, relais, worker, artefact
  canonique et lecture publique.

### Négatives ou coûts

- La conversion peut mobiliser Gemma pour chaque page Granite explicitement
  échouée.

### Risques et contrôles

- Risque : masquer Granite. Contrôle : trace Granite obligatoire dans chaque
  page Gemma et aucune répétition Granite.
- Risque : faire de Gemma un fallback général. Contrôle : ensemble fermé de
  deux codes déclencheurs, testé explicitement.
- Risque : publier une sortie Gemma incomplète. Contrôle : validation stricte
  du texte, du modèle et des coordonnées avant la QA canonique.
- Risque : masquer une seconde tentative Gemma. Contrôle : elle est limitée à
  l'erreur de contrat de coordonnées du rendu initial, à 90 degrés, une seule
  fois, et elle est inscrite dans la version de l'outil canonique.

## Impact d'implémentation

- Modules concernés : politique de récupération Granite/Gemma, worker routé
  M-004, contrat de progression publique et UI de conversion.
- Configuration concernée : aucune nouvelle dépendance ni clé ; le chemin
  `llm-gateway` existant est réemployé, `models.llm.max_output_tokens` vaut
  4 096 et le délai client est dérivé du timeout et du nombre de retries
  explicitement configurés.
- Tests attendus : déclencheur `GRANITE_DOCLING_UNAVAILABLE`, absence de
  récupération pour un code hors contrat, seconde tentative 90 degrés bornée
  après bbox invalide, repère de coordonnées restauré, trace canonique,
  progression et parcours UI réel complet.
- Milestones concernées : M-004, M-013.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0008_recuperer_gemma_apres_echec_terminal_granite.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m004/validate_granite_gemma_recovery_unit.py`.
- Commits : RED et GREEN à renseigner.

## Notes

La décision ne transforme pas un échec en succès synthétique : Gemma est un
second outil explicitement contractuel, dont l'appel, l'issue et la provenance
sont persistés et lus publiquement.
