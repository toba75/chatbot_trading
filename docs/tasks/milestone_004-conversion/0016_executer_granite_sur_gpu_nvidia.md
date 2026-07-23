# T-016 - Exécuter Granite sur le GPU NVIDIA local

## Scénario BDD

**Given** le worker documentaire courant reçoit une page routée vers
Granite-Docling et Docker expose la RTX 4090

**When** le sous-processus Granite démarre la conversion

**Then** il sélectionne explicitement `cuda:0`, produit une activité GPU réelle
et refuse l'exécution avec `GRANITE_CUDA_UNAVAILABLE` si CUDA est absent, sans
fallback CPU.

## Critères d'acceptation

- Le conteneur `worker-documents` reçoit explicitement le GPU NVIDIA.
- PyTorch voit CUDA et identifie la RTX 4090 depuis l'image worker.
- `VlmPipelineOptions` cible `cuda:0`, jamais `auto`.
- CUDA absent produit `GRANITE_CUDA_UNAVAILABLE` avant chargement du modèle.
- Le cache de compilation Triton utilise un `tmpfs` exécutable dédié de
  128 MiB et n'écrit pas dans `/workspace` en lecture seule.
- La cible d'image `worker-documents` contient le compilateur et les en-têtes C
  requis par Triton sans les ajouter aux autres cibles applicatives.
- Docling standard et les règles de récupération Gemma ne sont pas modifiés.
- Une page Granite réelle termine sans erreur avec une activité GPU observée.
- Le temps de conversion de la page est publié comme mesure, sans promettre un
  gain avant comparaison.
- Le scope M-004 et la gouvernance sont GREEN.

## ADR

- ADR-051.

## Preuves d'exécution

- GREEN initial : `uv run --locked gate --scope m004`, 44 nœuds uniques.
- RED : le test d'acceptation échoue parce que `_required_cuda_device` est
  absent ; commit `436c682e9`.
- Image : PyTorch `2.13.0+cu130`, CUDA 13.0, un périphérique visible nommé
  `NVIDIA GeForce RTX 4090 Laptop GPU`.
- Live positif : page 2 du PDF de qualification, route `MIXED_PAGEWISE`, code
  0 en 21,315 secondes, deux items et provenance `granite_docling`.
- Mesure pendant l'inférence : 42 % GPU, 1 360 MiB de VRAM, environ 41 W.
- Live négatif : même payload sans GPU, code 1 et
  `GRANITE_CUDA_UNAVAILABLE`.
- Image finale : sans injection manuelle de `TRITON_CACHE_DIR`, code 0 en
  19,266 secondes et `TRITON_CACHE_DIR=/triton-cache` fourni par l'image.
