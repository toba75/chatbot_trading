"""Registre bibliographique, temporel et éditorial du corpus RAG."""

from .registry import (
    CATALOG,
    CATALOG_SCHEMA_VERSION,
    build_skeleton,
    load_catalog,
    save_catalog,
    validate_catalog,
)

__all__ = [
    "CATALOG",
    "CATALOG_SCHEMA_VERSION",
    "build_skeleton",
    "load_catalog",
    "save_catalog",
    "validate_catalog",
]
