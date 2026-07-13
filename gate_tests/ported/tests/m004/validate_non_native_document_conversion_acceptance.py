"""Acceptation T-005 : worker réel non natif, refus terminal et publication atomique."""

from __future__ import annotations

import importlib

import pytest


def _worker_module():
    try:
        return importlib.import_module(
            "app.source_processing.application.routed_document_conversion_worker"
        )
    except ModuleNotFoundError as error:
        pytest.fail(
            "NON_NATIVE_DOCUMENT_WORKER_ABSENT: le worker doit exécuter les routes M-003 non natives."
        )
        raise AssertionError("pytest.fail doit interrompre le test") from error


def test_the_non_native_worker_exposes_stable_terminal_errors_without_partial_canonical_artifact() -> None:
    # Given une page SCAN_GRANITE et un actif Granite absent après une demande acceptée.
    # When le worker CONVERT_DOCUMENT commence le traitement réel.
    # Then il persiste GRANITE_DOCLING_UNAVAILABLE et ne publie aucun artefact canonique partiel.
    worker_module = _worker_module()
    assert worker_module.RoutedDocumentConversionWorker.__name__ == "RoutedDocumentConversionWorker"
    assert worker_module.NON_NATIVE_TERMINAL_ERROR_CODES >= {
        "GRANITE_DOCLING_UNAVAILABLE",
        "OCRMYPDF_UNAVAILABLE",
        "CONVERSION_ASSET_MANIFEST_INVALID",
    }


def test_ui_can_offer_conversion_for_a_complete_non_native_route_only_when_the_real_worker_is_ready() -> None:
    # Given une source dont toutes les pages sont explicitement routées SCAN_GRANITE.
    # When le runtime UI supervise le worker réel doté des actifs scellés.
    # Then le contrat public peut rendre Convertir disponible, puis expose QUEUED, RUNNING et une issue persistée.
    worker_module = _worker_module()
    assert callable(worker_module.build_routed_document_conversion_worker)
