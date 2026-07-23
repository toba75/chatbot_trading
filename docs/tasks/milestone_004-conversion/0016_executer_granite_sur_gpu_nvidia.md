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
- Docling standard et les règles de récupération Gemma ne sont pas modifiés.
- Une page Granite réelle termine sans erreur avec une activité GPU observée.
- Le temps de conversion de la page est publié comme mesure, sans promettre un
  gain avant comparaison.
- Le scope M-004 et la gouvernance sont GREEN.

## ADR

- ADR-051.

