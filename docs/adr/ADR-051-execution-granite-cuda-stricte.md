# ADR-051 - Exécution Granite-Docling CUDA stricte

**Statut :** Proposée
**Date :** 2026-07-23
**Décideurs :** Équipe OSTrading
**Remplace :** Pour le périphérique Granite du worker documentaire local, la sélection automatique implicite de Docling
**Remplacée par :** Aucune
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
- Commits : RED à produire ; GREEN à produire.

## Notes

L'ADR ne promet pas à elle seule un gain de performance. La décision rend le
périphérique certain ; le gain doit être mesuré sur une page Granite réelle.

