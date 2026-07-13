# T-003 - Convertir et fusionner les pages selon la route explicite

## Milestone
- Nom: M-004 - Version canonique publiée.
- Source: livrables M-004 du plan v4.1 et ADR-002, ADR-003.
- Objectif métier: transformer un plan de routage M-003 en sorties de conversion auditables puis en DoclingDocument unique sans choix implicite de chaîne documentaire.

## Contexte DDD
- Domaine: conversion documentaire contrôlée.
- Bounded context: `SP`.
- Objectif métier: exécuter la route déjà décidée pour chaque page, conserver les sorties concurrentes nécessaires à l'audit et assembler les pages dans un DoclingDocument canonique unique.
- Langage ubiquitaire: route de page, Docling standard, Granite-Docling, prétraitement OCRmyPDF conditionnel, sortie de conversion, fusion pagewise, item canonique, coordonnées normalisées, lien de provenance, artefact d'audit, version de politique.
- Invariants critiques: chaque page routée produit exactement les sorties attendues par sa route; OCRmyPDF n'est appelé que si la route l'autorise; une route inconnue ou absente bloque la conversion; la fusion conserve l'ordre des pages, des item ids uniques, les labels, tables, figures, coordonnées et liens vers le PDF original.
- Garde-fous: aucun fallback silencieux entre Docling et Granite; aucun OCR systématique; aucune conversion d'une source en quarantaine ou d'une tentative non `ROUTE_PLANNED`; aucun DoclingDocument publié si une page, un item id ou une provenance manque.

## Blocages Ou Préconditions
- État GREEN/RED connu: T-001 et T-002 doivent être GREEN.
- Présence des milestones amont dans master: M-000 à M-003 sont présents dans `master`.
- Décisions manquantes: une ADR est requise si une nouvelle route de conversion devient normative; les routes M-003 existantes appliquent ADR-002 et ADR-003.
- Risques: utiliser Docling comme modèle de domaine; convertir une page non routée; remplacer une erreur d'adaptateur par une autre route non demandée; produire des sorties par page sans DoclingDocument unique exploitable par la publication canonique.

## Tâches
### T-003 - Convertir et fusionner les pages selon la route explicite
- But métier: produire les candidats de texte et structure pour chaque page, puis les assembler dans un DoclingDocument unique sans perdre la justification du routage.
- Portée DDD: ports applicatifs SP de conversion, adaptateurs Docling, Granite-Docling et OCRmyPDF conditionnel, modèle de sortie de conversion pagewise, composant de fusion pagewise et journal d'audit par page.
- Scénario BDD:
  - Given un `DocumentProcessingRun` M-003 avec un `RoutePlan` approuvé pour toutes les pages.
  - When la conversion documentaire M-004 est demandée.
  - Then chaque page est convertie uniquement par la route explicitement planifiée, chaque sortie conserve route, outil, version, hash et justification, puis la fusion pagewise crée un DoclingDocument unique qui conserve ordre, item ids, labels, tables, figures, coordonnées et provenance.
- Tests d'acceptation à écrire: un test `uv run --locked gate` couvrant un document mixte avec routes native, Granite et prétraitement conditionnel, la fusion pagewise dans un DoclingDocument unique, plus le refus d'une route absente, d'une source quarantinée ou d'une page sans provenance.
- Tests unitaires à écrire: tests des ports de conversion, mapping route vers adaptateur, refus OCRmyPDF sans route `PREPROCESS_GRANITE`, conservation des artefacts d'audit, propagation explicite des erreurs d'adaptateur, unicité des item ids, ordre strict des pages, coordonnées normalisées et liens de provenance obligatoires.
- Implémentation attendue: créer les abstractions de conversion SP, les résultats pagewise, les adaptateurs minces, les fixtures de sorties Docling/Granite, le service de fusion pagewise et l'orchestration qui ne choisit jamais de route à la place du domaine.
- Invariants et garde-fous: route obligatoire; outil et version obligatoires; hash d'artefact obligatoire; item_id canonique unique; provenance obligatoire pour chaque item; aucune chaîne alternative déclenchée après échec; aucun original modifié.
- Dépendances: T-002; M-003 `RoutePlan`; ADR-002; ADR-003; `app/source_processing/domain/document_processing_run.py`.
- Commandes de validation: `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`; `uv run --locked gate`.
- Commit RED: `test(m004): couvrir la conversion et fusion pagewise`.
- Commit GREEN: `feat(m004): convertir et fusionner les pages routees`.
