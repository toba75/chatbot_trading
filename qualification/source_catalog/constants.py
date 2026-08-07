"""Constantes partagées par le registre et son validateur."""

from pathlib import Path
import re

CATALOG_SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
CATALOG_DIR = ROOT / "docs" / "source_catalog"
CATALOG = CATALOG_DIR / "catalog.json"
SCHEMA = CATALOG_DIR / "schema.json"
POLICY = CATALOG_DIR / "persistence-policy.md"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
QUERY_STATES = {"not_queried", "succeeded", "no_match", "unavailable", "expired"}
RESOLUTION_STATES = {"not_queried", "candidate", "accepted", "ambiguous", "rejected", "no_match", "unavailable"}
EDITORIAL_STATES = {"reviewed", "not_assessable"}
