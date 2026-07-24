# ADR-051 - Exécution Granite-Docling CUDA stricte

**Statut :** Acceptée
**Date :** 2026-07-23
**Décideurs :** Équipe OSTrading
**Remplace :** Pour le périphérique Granite du worker documentaire local, la sélection automatique implicite de Docling
**Remplacée par :** Partiellement par ADR-052 pour M-014 uniquement ; les exigences `cuda:0`, `GRANITE_CUDA_UNAVAILABLE` et sans fallback restent applicables
**Source :** Demande utilisateur du 2026-07-23 d'exécuter le worker Granite actuel sur la RTX 4090

## Contexte

Le sous-processus Granite-Docling construit actuellement ses options VLM sans
indiquer de périphérique. Docling applique alors sa valeur `auto` : CUDA est
utilisé lorsqu'il est disponible, mais une exécution CPU peut être sélectionnée
implicitement. Cette ambiguïté empêche de prouver que Granite utilise réellement
la RTX 4090 et peut expliquer une conversion trop lente.

La station locale expose une NVIDIA GeForce RTX 4090 Laptop GPU à Docker par le
runtime NVIDIA. L'image Linux verrouillée du worker documentaire contient
PyTorch compilé avec CUDA. Le changement doit concerner Granite seulement :
Docling standard conserve son exécution actuelle et Gemma reste sur le gateway
prévu par les ADR applicables.

Le plan M-014 conserve une première flotte réseau CPU multiarchitecture. Cette
flotte est un livrable distinct du worker Granite CUDA courant et ne doit pas
recevoir implicitement une exigence NVIDIA.

## Décision

- Le conteneur local `worker-documents` **DOIT** recevoir explicitement les GPU
  NVIDIA publiés par Docker.
- Chaque sous-processus Granite-Docling du worker courant **DOIT** sélectionner
  `cuda:0` au moyen des options d'accélération Docling.
- Le worker **DOIT** vérifier avant le chargement du modèle que PyTorch a été
  compilé avec CUDA, que CUDA est disponible et que le périphérique zéro existe.
- Le cache de compilation Triton **DOIT** être écrit dans un `tmpfs` dédié,
  exécutable, borné à 128 MiB, sans `suid` ni périphérique et accessible
  uniquement à `root` et au groupe stable `31000` du worker ; le filesystem
  applicatif reste en lecture seule et le `tmpfs` général `/tmp` reste non
  exécutable.
- L'image du worker documentaire **DOIT** fournir le compilateur et les en-têtes
  de la bibliothèque C requis par Triton, sans les ajouter aux images de l'API
  ou des autres workers.
- Si l'une de ces conditions manque, Granite **DOIT** terminer avec le code
  stable `GRANITE_CUDA_UNAVAILABLE`.
- Granite **NE DOIT PAS** continuer sur CPU, sélectionner `auto`, ni changer de
  route en raison de l'indisponibilité CUDA.
- Docling standard **NE DOIT PAS** être déplacé sur GPU par ce changement.
- La preuve live **DOIT** identifier le périphérique NVIDIA visible depuis
  l'image worker et convertir une page Granite réelle avec une activité GPU
  observée.
- Les workers CPU multiarchitectures de M-014 **DOIVENT** rester des images et
  profils explicites distincts. Leur décision structurante relève d'ADR-052.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| Conserver `auto` | Rejetée | Autorise un fallback CPU silencieux et ne prouve pas l'accélérateur réel. |
| Définir `cuda:0` et exiger le GPU dans le conteneur | Retenue | Rend l'intention vérifiable et transforme l'absence de CUDA en erreur stable. |
| Déplacer aussi Docling standard sur GPU | Rejetée | Élargit le changement sans preuve que cette route en bénéficie. |
| Rendre tous les futurs workers réseau dépendants de NVIDIA | Rejetée | Exclut les Mac Apple Silicon et contredit la flotte CPU initiale de M-014. |

## Conséquences

### Positives

- Granite utilise explicitement la RTX 4090 du poste courant.
- Une absence de GPU ne peut plus être confondue avec une conversion Granite
  lente sur CPU.
- L'effet sur le temps de conversion peut être mesuré avec la même page et les
  mêmes actifs scellés.

### Négatives ou coûts

- Les trois profils locaux exigent un runtime Docker NVIDIA pour démarrer le
  worker documentaire courant.
- Le worker documentaire devient dépendant du GPU sur cette station, même pour
  un document qui ne rencontrera finalement aucune route Granite.
- La flotte CPU M-014 nécessitera un profil worker-only distinct.

### Risques et contrôles

- Risque de GPU visible mais non utilisé : options Docling fixées à `cuda:0` et
  preuve live d'activité GPU pendant une conversion réelle.
- Risque d'échec de compilation Triton sur le filesystem en lecture seule :
  `TRITON_CACHE_DIR=/triton-cache` dans un `tmpfs` exécutable dédié et borné.
- Risque d'image inutilement élargie : `gcc` et `libc6-dev` sont installés dans
  la seule cible Docker `worker-documents`.
- Risque de fallback CPU : interdiction de `auto` et erreur
  `GRANITE_CUDA_UNAVAILABLE` testée.
- Risque de contention entre deux processus Granite : les plafonds d'ADR-040
  et ADR-042 restent applicables et la concurrence demeure fixée à deux.
- Risque de rendre les Mac incompatibles : images CPU M-014 séparées, sans
  détection automatique de CUDA ou MPS.

## Impact d'implémentation

- Modules concernés : worker Granite isolé et Compose du worker documentaire.
- Configuration concernée : réservation GPU du service `worker-documents` et
  options d'accélération `VlmPipelineOptions`.
- Tests attendus : sélection `cuda:0`, refus sans CUDA, inspection Compose,
  visibilité PyTorch CUDA dans le conteneur et conversion Granite live.
- Milestones concernées : M-004 conversion ; précondition de mesure pour M-014.

## Liens de traçabilité

- Spécification : `docs/specs/m004_version_canonique_publiee.md`.
- Plan d'implémentation :
  `docs/tasks/milestone_004-conversion/0016_executer_granite_sur_gpu_nvidia.md`.
- Tests d'acceptation :
  `gate_tests/ported/tests/m004/validate_granite_cuda_runtime_acceptance.py`.
- Commits : RED `436c682e9` ; GREEN présent commit.

## Notes

Cette ADR est partiellement remplacée par ADR-052 pour M-014 uniquement sur
les mentions historiques d’une flotte CPU multiarchitecture ou distante. Ce
lien réciproque est conditionnel au périmètre M-014 et ne change aucune
exigence d’exécution Granite CUDA stricte de la présente ADR.

L'ADR ne promet pas à elle seule un gain de performance. La décision rend le
périphérique certain ; le gain doit être mesuré sur une page Granite réelle.

La preuve d'acceptation exécute la page 2 du PDF de qualification M-013, route
`MIXED_PAGEWISE`, dans l'image Linux du worker. PyTorch 2.13.0+cu130 identifie
la NVIDIA GeForce RTX 4090 Laptop GPU. Pendant l'inférence, la mesure atteint
42 % d'utilisation, 1 360 MiB de VRAM et environ 41 W. La conversion termine
avec le code 0 en 21,315 secondes, publie deux items pour la page 2 et conserve
uniquement la provenance `granite_docling`. Le même payload sans GPU termine
avec `GRANITE_CUDA_UNAVAILABLE` et le code 1.

Une seconde exécution sur l'image finale, sans injection manuelle de
`TRITON_CACHE_DIR`, termine avec le code 0 en 19,266 secondes et confirme
`TRITON_CACHE_DIR=/triton-cache` dans la configuration de l'image.
