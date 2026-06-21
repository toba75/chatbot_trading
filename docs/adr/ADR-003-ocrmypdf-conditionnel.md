# ADR-003 - OCRmyPDF conditionnel

**Statut :** Acceptée
**Date :** 2026-06-21
**Décideurs :** Propriétaire du projet
**Remplace :** Aucun
**Remplacée par :** Aucune
**Source :** `docs/specs/specification_unifiee_ddd_technique_chatbot_trading_v4_1.md`, section 3, ADR-003

## Contexte

Certains scans nécessitent une correction physique avant conversion. Appliquer OCRmyPDF à tout le corpus introduirait une couche textuelle non contrôlée et des altérations inutiles.

## Décision

OCRmyPDF NE DOIT PAS être appliqué à tous les PDF.

Il PEUT intervenir uniquement comme prétraitement conditionnel pour corriger rotation, redressement, nettoyage prudent ou réparation exceptionnelle d'une couche OCR. Sa sortie n'est pas le format final du système.

## Options considérées

| Option | Statut | Raisons |
|---|---|---|
| OCRmyPDF systématique | Rejetée | Introduit une transcription concurrente et des coûts inutiles. |
| Interdiction totale d'OCRmyPDF | Rejetée | Bloque les scans physiquement dégradés. |
| Usage conditionnel explicite | Retenue | Permet la correction sans perdre l'autorité du Docling JSON. |

## Conséquences

### Positives

- Les scans dégradés restent traitables.
- L'autorité textuelle reste décidée explicitement.

### Négatives ou coûts

- Le diagnostic doit justifier l'usage d'OCRmyPDF.
- Les artefacts de prétraitement doivent être conservés pour audit.

### Risques et contrôles

- Risque: une couche OCR prétraitée devient autorité sans adjudication. Contrôle: ADR-004 et tests d'autorité textuelle.

## Impact d'implémentation

- Modules concernés: `source_processing.adapters`.
- Configuration concernée: politique de prétraitement.
- Tests attendus: OCRmyPDF refusé sans diagnostic admissible.
- Milestones concernées: M-003, M-004.

## Liens de traçabilité

- Spécification: sections 3 et 5.
- Plan d'implémentation: M-004.
- Tests d'acceptation: conversion hybride et QA documentaire.
- Commits: à renseigner lors de l'implémentation.
