from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


DOMAIN_FORBIDDEN_EXTERNAL_IMPORTS: dict[str, str] = {
    "django": "framework web",
    "docling": "bibliothèque Docling",
    "fastapi": "framework web",
    "flask": "framework web",
    "litestar": "framework web",
    "openai": "SDK modèle externe",
    "pydantic": "modèle API",
    "qdrant_client": "client Qdrant",
    "sqlalchemy": "ORM",
    "sqlmodel": "ORM et modèle API",
    "starlette": "framework web",
    "vllm": "SDK vLLM",
}

DOMAIN_API_MODEL_BASES = {"BaseModel", "SQLModel"}
CONTEXT_LAYERS = {"domain", "application", "adapters"}
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SPECIAL_SOURCE_CONTRACTS = "CONTRACTS"
SPECIAL_SOURCE_PLATFORM = "PLATFORM"
ALL_CONTEXT_CODES = frozenset({"SP", "KA", "EG", "RA", "CV", "SD", "EX", "EV"})
SOURCE_REFERENCE_CONSUMERS = frozenset({"SP", "KA", "EG", "RA", "CV", "EV"})
EVIDENCE_CLAIM_CONSUMERS = frozenset({"EG", "RA", "SD"})
RESEARCH_OUTCOME_CONSUMERS = frozenset({"RA", "SD"})
STRATEGY_SNAPSHOT_CONSUMERS = frozenset({"SD", "EX"})
EXPERIMENT_RESULT_CONSUMERS = frozenset({"EX", "RA", "CV"})
QDRANT_DIRECT_ACCESS_FORBIDDEN_CONSUMERS = frozenset({"EG", "RA"})
ORCHESTRATOR_COMPOSITION_MODULE = "app.platform.orchestrator_runtime"
ORCHESTRATOR_COMPOSITION_ALLOWED_IMPORTS = frozenset(
    {
        "app.knowledge_access.adapters.http",
        "app.knowledge_access.adapters.postgres_projection_read",
        "app.knowledge_access.application.projection_queries",
        "app.source_processing.adapters.document_http",
        "app.source_processing.adapters.http",
        "app.source_processing.adapters.original_http",
        "app.source_processing.adapters.pdf_document_inspector",
        "app.source_processing.adapters.postgres_document_persistence",
        "app.source_processing.adapters.query_http",
        "app.source_processing.application.document_commands",
        "app.source_processing.application.document_queries",
        "app.source_processing.application.original_queries",
    }
)
CONTRACT_MODULE_ALLOWED_CONSUMERS: dict[str, frozenset[str]] = {
    "app.contracts.identity": ALL_CONTEXT_CODES,
    "app.contracts.source_references": SOURCE_REFERENCE_CONSUMERS,
    "app.contracts.evidence_claims": EVIDENCE_CLAIM_CONSUMERS,
    "app.contracts.research_outcomes": RESEARCH_OUTCOME_CONSUMERS,
    "app.contracts.event_envelope": ALL_CONTEXT_CODES,
    "app.contracts.document_public_statuses": ALL_CONTEXT_CODES,
    "app.contracts.technical_jobs": ALL_CONTEXT_CODES,
}
CONTRACT_SYMBOL_ALLOWED_CONSUMERS: dict[tuple[str, str], frozenset[str]] = {
    ("app.contracts", "ContractSchemaVersion"): ALL_CONTEXT_CODES,
    ("app.contracts", "DomainIdentifier"): ALL_CONTEXT_CODES,
    ("app.contracts", "serialize_contract_payload"): ALL_CONTEXT_CODES,
    ("app.contracts", "validate_contract_payload"): ALL_CONTEXT_CODES,
    ("app.contracts", "CanonicalSourceRef"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts.source_references", "CanonicalSourceRef"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts", "SourceLocator"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts.source_references", "SourceLocator"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts", "SourceLocatorValidationPolicy"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts.source_references", "SourceLocatorValidationPolicy"): SOURCE_REFERENCE_CONSUMERS,
    ("app.contracts", "EvidenceRef"): EVIDENCE_CLAIM_CONSUMERS,
    ("app.contracts.evidence_claims", "EvidenceRef"): EVIDENCE_CLAIM_CONSUMERS,
    ("app.contracts", "VerifiedClaimRef"): EVIDENCE_CLAIM_CONSUMERS,
    ("app.contracts.evidence_claims", "VerifiedClaimRef"): EVIDENCE_CLAIM_CONSUMERS,
    ("app.contracts", "VerifiedResearchOutcome"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts.research_outcomes", "VerifiedResearchOutcome"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts", "ResearchConflictRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts.research_outcomes", "ResearchConflictRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts", "KnowledgeGapRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts.research_outcomes", "KnowledgeGapRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts", "VersionedClaimRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts.research_outcomes", "VersionedClaimRef"): RESEARCH_OUTCOME_CONSUMERS,
    ("app.contracts", "StrategySnapshot"): STRATEGY_SNAPSHOT_CONSUMERS,
    ("app.contracts.strategy_experiments", "StrategySnapshot"): STRATEGY_SNAPSHOT_CONSUMERS,
    ("app.contracts", "ExperimentResult"): EXPERIMENT_RESULT_CONSUMERS,
    ("app.contracts.strategy_experiments", "ExperimentResult"): EXPERIMENT_RESULT_CONSUMERS,
    ("app.contracts", "EventEnvelope"): ALL_CONTEXT_CODES,
    ("app.contracts.event_envelope", "EventEnvelope"): ALL_CONTEXT_CODES,
    ("app.contracts", "EventIdempotenceDecision"): ALL_CONTEXT_CODES,
    ("app.contracts.event_envelope", "EventIdempotenceDecision"): ALL_CONTEXT_CODES,
    ("app.contracts", "EventIdempotenceLedger"): ALL_CONTEXT_CODES,
    ("app.contracts.event_envelope", "EventIdempotenceLedger"): ALL_CONTEXT_CODES,
}
CONTRACT_SYMBOL_REQUIRED_MODULES = frozenset({"app.contracts", "app.contracts.strategy_experiments"})
PUBLISHED_CONTRACT_SYMBOL_KEYS: dict[str, tuple[tuple[str, str], ...]] = {
    "VerifiedClaimRef": (
        ("app.contracts", "VerifiedClaimRef"),
        ("app.contracts.evidence_claims", "VerifiedClaimRef"),
    ),
    "VerifiedResearchOutcome": (
        ("app.contracts", "VerifiedResearchOutcome"),
        ("app.contracts.research_outcomes", "VerifiedResearchOutcome"),
    ),
    "StrategySnapshot": (
        ("app.contracts", "StrategySnapshot"),
        ("app.contracts.strategy_experiments", "StrategySnapshot"),
    ),
    "ExperimentResult": (
        ("app.contracts", "ExperimentResult"),
        ("app.contracts.strategy_experiments", "ExperimentResult"),
    ),
}


@dataclass(frozen=True)
class ContextDefinition:
    code: str
    module: str
    layers: frozenset[str]


@dataclass(frozen=True)
class SourceModule:
    path: Path
    module_name: str
    context_code: str
    context_module: str
    layer: str | None


@dataclass(frozen=True)
class ImportedModule:
    name: str
    kind: str
    context_code: str | None
    context_module: str | None
    layer: str | None


@dataclass(frozen=True)
class ImportReference:
    module_name: str
    symbol_names: tuple[str, ...]
    line_number: int


@dataclass(frozen=True)
class PublishedRelation:
    relation_source: str
    relation_target: str
    producer: str
    consumer: str
    contract: str
    status: str
    relation_type: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Valide les frontières d'import M-001 entre bounded contexts."
    )
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--context-registry-path", required=True)
    parser.add_argument("--specification-path", required=True)
    return parser.parse_args()


def require_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ValueError(f"{label} absent: {path}")


def require_directory(path: Path, label: str) -> None:
    if not path.is_dir():
        raise ValueError(f"{label} absent: {path}")


def require_path_under_repository(path: Path, label: str) -> None:
    try:
        path.relative_to(REPOSITORY_ROOT)
    except ValueError as exc:
        raise ValueError(f"Chemin hors depot interdit ({label}): {path}") from exc


def load_context_definitions(registry_path: Path) -> tuple[dict[str, ContextDefinition], dict[str, ContextDefinition]]:
    require_file(registry_path, "Registre de contextes")
    registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))

    contexts_by_code: dict[str, ContextDefinition] = {}
    contexts_by_module: dict[str, ContextDefinition] = {}

    for context_payload in registry["contexts"]:
        code = str(context_payload["code"])
        module = str(context_payload["module"])
        layers = frozenset(str(layer) for layer in context_payload["layers"])

        if code in contexts_by_code:
            raise ValueError(f"Contexte dupliqué dans le registre: {code}")
        if module in contexts_by_module:
            raise ValueError(f"Module de contexte dupliqué dans le registre: {module}")
        if layers != CONTEXT_LAYERS:
            raise ValueError(f"Couches invalides pour {code}: {sorted(layers)}")

        context = ContextDefinition(code=code, module=module, layers=layers)
        contexts_by_code[code] = context
        contexts_by_module[module] = context

    return contexts_by_code, contexts_by_module


def validate_app_root_structure(
    app_root: Path,
    contexts_by_module: dict[str, ContextDefinition],
) -> None:
    require_file(app_root / "__init__.py", "Package app")
    require_directory(app_root / "contracts", "Module contracts")
    require_file(app_root / "contracts" / "__init__.py", "Package contracts")
    require_directory(app_root / "platform", "Module platform")
    require_file(app_root / "platform" / "__init__.py", "Package platform")

    for context in contexts_by_module.values():
        context_root = app_root / context.module
        require_directory(context_root, f"Module de contexte absent: {context.module}")
        require_file(context_root / "__init__.py", f"Package de contexte absent: {context.module}")
        for layer in sorted(context.layers):
            layer_root = context_root / layer
            require_directory(layer_root, f"Couche de contexte absente: {context.module}/{layer}")
            require_file(
                layer_root / "__init__.py",
                f"Package de couche absent: {context.module}/{layer}",
            )


def normalize_markdown_cell(value: str) -> str:
    normalized = value.strip()
    normalized = normalized.replace("`", "")
    normalized = normalized.replace("**", "")
    normalized = re.sub(r"<br\s*/?>", " ", normalized)
    return normalized


def split_markdown_row(line: str) -> list[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [normalize_markdown_cell(cell) for cell in stripped.split("|")]


def is_markdown_separator(line: str) -> bool:
    return re.fullmatch(r"\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?", line.strip()) is not None


def read_markdown_table(lines: list[str], required_headers: set[str], table_name: str) -> list[dict[str, str]]:
    for line_index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            continue

        headers = split_markdown_row(line)
        if not required_headers.issubset(set(headers)):
            continue

        separator_index = line_index + 1
        if separator_index >= len(lines) or not is_markdown_separator(lines[separator_index]):
            raise ValueError(f"Table {table_name} invalide: séparateur absent.")

        rows: list[dict[str, str]] = []
        row_index = line_index + 2
        while row_index < len(lines) and lines[row_index].strip().startswith("|"):
            if is_markdown_separator(lines[row_index]):
                row_index += 1
                continue

            cells = split_markdown_row(lines[row_index])
            if len(cells) != len(headers):
                raise ValueError(f"Table {table_name} invalide: ligne {row_index + 1}.")

            rows.append({headers[cell_index]: cells[cell_index] for cell_index in range(len(headers))})
            row_index += 1

        if len(rows) == 0:
            raise ValueError(f"Table {table_name} invalide: aucune ligne.")

        return rows

    raise ValueError(f"Table {table_name} absente.")


def parse_relation_codes(relation: str) -> tuple[str, str]:
    normalized = relation.replace(" ", "")
    match = re.fullmatch(r"([A-Z]{2})->([A-Z]{2})", normalized)
    if match is None:
        raise ValueError(f"Relation M-001 invalide: {relation}")
    return match.group(1), match.group(2)


def load_published_relations(specification_path: Path) -> list[PublishedRelation]:
    require_file(specification_path, "Spécification M-001")
    lines = specification_path.read_text(encoding="utf-8-sig").splitlines()
    relation_rows = read_markdown_table(
        lines=lines,
        required_headers={
            "Relation",
            "Producteur",
            "Consommateur",
            "Contrat publié",
            "Statut M-001",
            "Type",
            "Modèle interne interdit",
        },
        table_name="relations intercontextes publiées",
    )

    relations: list[PublishedRelation] = []
    for row in relation_rows:
        relation_source, relation_target = parse_relation_codes(row["Relation"])
        relations.append(
            PublishedRelation(
                relation_source=relation_source,
                relation_target=relation_target,
                producer=row["Producteur"],
                consumer=row["Consommateur"],
                contract=row["Contrat publié"],
                status=row["Statut M-001"],
                relation_type=row["Type"],
            )
        )

    return relations


def validate_contract_consumer_rules(relations: list[PublishedRelation]) -> None:
    expected_consumers_by_contract: dict[str, set[str]] = {}
    for relation in relations:
        if relation.contract not in PUBLISHED_CONTRACT_SYMBOL_KEYS:
            continue
        if relation.status != "Livré":
            continue
        expected_consumers = expected_consumers_by_contract.setdefault(relation.contract, set())
        expected_consumers.add(relation.producer)
        expected_consumers.add(relation.consumer)

    for contract, symbol_keys in PUBLISHED_CONTRACT_SYMBOL_KEYS.items():
        if contract not in expected_consumers_by_contract:
            continue
        expected_consumers = frozenset(expected_consumers_by_contract[contract])
        for symbol_key in symbol_keys:
            actual_consumers = CONTRACT_SYMBOL_ALLOWED_CONSUMERS.get(symbol_key)
            if actual_consumers == expected_consumers:
                continue
            actual_value = sorted(actual_consumers) if actual_consumers is not None else []
            raise ValueError(
                "Regle de contrat publie incoherente avec specification M-001: "
                f"{contract}, symbole {symbol_key[1]}, attendu {sorted(expected_consumers)}, "
                f"obtenu {actual_value}."
            )


def python_module_name(app_root: Path, path: Path) -> str:
    relative = path.relative_to(app_root)
    parts = ["app", *relative.parts]
    last_part = parts[-1]
    if last_part == "__init__.py":
        return ".".join(parts[:-1])
    parts[-1] = last_part[:-3]
    return ".".join(parts)


def classify_source_module(
    app_root: Path,
    path: Path,
    contexts_by_module: dict[str, ContextDefinition],
) -> SourceModule | None:
    relative = path.relative_to(app_root)
    parts = relative.parts
    if len(parts) == 0:
        return None

    if parts[0] == "contracts":
        return SourceModule(
            path=path,
            module_name=python_module_name(app_root, path),
            context_code=SPECIAL_SOURCE_CONTRACTS,
            context_module="contracts",
            layer=None,
        )

    if parts[0] == "platform":
        return SourceModule(
            path=path,
            module_name=python_module_name(app_root, path),
            context_code=SPECIAL_SOURCE_PLATFORM,
            context_module="platform",
            layer=None,
        )

    context = contexts_by_module.get(parts[0])
    if context is None:
        return None

    layer = parts[1] if len(parts) > 1 and parts[1] in context.layers else None
    return SourceModule(
        path=path,
        module_name=python_module_name(app_root, path),
        context_code=context.code,
        context_module=context.module,
        layer=layer,
    )


def classify_import(name: str, contexts_by_module: dict[str, ContextDefinition]) -> ImportedModule:
    if name == "app.contracts" or name.startswith("app.contracts."):
        return ImportedModule(name=name, kind="contracts", context_code=None, context_module=None, layer=None)

    if name == "app.platform" or name.startswith("app.platform."):
        return ImportedModule(name=name, kind="platform", context_code=None, context_module="platform", layer=None)

    if not name.startswith("app."):
        return ImportedModule(name=name, kind="external", context_code=None, context_module=None, layer=None)

    parts = name.split(".")
    if len(parts) < 2:
        return ImportedModule(name=name, kind="app_root", context_code=None, context_module=None, layer=None)

    context = contexts_by_module.get(parts[1])
    if context is None:
        return ImportedModule(name=name, kind="unknown_app_module", context_code=None, context_module=parts[1], layer=None)

    layer = parts[2] if len(parts) > 2 and parts[2] in context.layers else None
    return ImportedModule(
        name=name,
        kind="bounded_context",
        context_code=context.code,
        context_module=context.module,
        layer=layer,
    )


def source_package_parts(source: SourceModule) -> list[str]:
    parts = source.module_name.split(".")
    if source.path.name == "__init__.py":
        return parts
    return parts[:-1]


def resolve_import_from_module(source: SourceModule, node: ast.ImportFrom) -> str:
    if node.level == 0:
        return node.module or ""

    package_parts = source_package_parts(source)
    if node.level > len(package_parts):
        raise ValueError(f"Import relatif invalide dans {source.path}: niveau {node.level}")

    base_parts = package_parts[: len(package_parts) - node.level + 1]
    if node.module:
        base_parts.extend(node.module.split("."))
    return ".".join(base_parts)


def imported_references(source: SourceModule, tree: ast.AST) -> list[ImportReference]:
    imports: list[ImportReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportReference(
                        module_name=alias.name,
                        symbol_names=(),
                        line_number=node.lineno,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module_name = resolve_import_from_module(source, node)
            if module_name:
                imports.append(
                    ImportReference(
                        module_name=module_name,
                        symbol_names=tuple(alias.name for alias in node.names),
                        line_number=node.lineno,
                    )
                )
    return imports


def class_base_name(base: ast.expr) -> str:
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        names = [base.attr]
        value = base.value
        while isinstance(value, ast.Attribute):
            names.append(value.attr)
            value = value.value
        if isinstance(value, ast.Name):
            names.append(value.id)
        return ".".join(reversed(names))
    if isinstance(base, ast.Subscript):
        return class_base_name(base.value)
    return ""


def find_domain_api_models(source: SourceModule, tree: ast.AST) -> list[str]:
    if source.layer != "domain":
        return []

    forbidden_classes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        for base in node.bases:
            base_name = class_base_name(base)
            short_base_name = base_name.split(".")[-1]
            if short_base_name in DOMAIN_API_MODEL_BASES:
                forbidden_classes.append(
                    f"Modèle d'API interdit dans domain: contexte {source.context_code}, "
                    f"module {source.module_name}, classe {node.name} hérite de {base_name}."
                )

    return forbidden_classes


def related_relations(source_code: str, target_code: str, relations: list[PublishedRelation]) -> list[PublishedRelation]:
    pair = {source_code, target_code}
    return [
        relation
        for relation in relations
        if {relation.producer, relation.consumer} == pair
        or {relation.relation_source, relation.relation_target} == pair
    ]


def expected_contracts(source_code: str, target_code: str, relations: list[PublishedRelation]) -> str:
    contracts = sorted({relation.contract for relation in related_relations(source_code, target_code, relations)})
    if len(contracts) == 0:
        return "aucun contrat publié documenté"
    return ", ".join(contracts)


def is_facade_relation(relation: PublishedRelation) -> bool:
    normalized = relation.relation_type.lower().replace("ç", "c")
    return "facade applicative" in normalized


def allows_facade_import(
    source: SourceModule,
    target: ImportedModule,
    relations: list[PublishedRelation],
) -> bool:
    if target.layer != "application":
        return False
    if source.layer not in {"application", "adapters"}:
        return False

    return any(
        is_facade_relation(relation)
        and relation.relation_source == source.context_code
        and relation.relation_target == target.context_code
        for relation in relations
    )


def contract_module_key(import_name: str) -> str:
    if import_name == "app.contracts":
        return "app.contracts"

    parts = import_name.split(".")
    if len(parts) >= 3:
        return ".".join(parts[:3])

    return import_name


def format_source_location(source: SourceModule, line_number: int) -> str:
    try:
        relative_path = source.path.relative_to(REPOSITORY_ROOT)
    except ValueError:
        relative_path = source.path
    return f"{relative_path}:{line_number}"


def format_import_reference(target: ImportedModule, import_reference: ImportReference) -> str:
    if len(import_reference.symbol_names) == 0:
        return target.name
    return f"{target.name} import {', '.join(import_reference.symbol_names)}"


def allowed_contract_consumers(
    target: ImportedModule,
    symbol_name: str,
) -> frozenset[str] | None:
    symbol_allowed_consumers = CONTRACT_SYMBOL_ALLOWED_CONSUMERS.get((target.name, symbol_name))
    if symbol_allowed_consumers is not None:
        return symbol_allowed_consumers

    if target.name in CONTRACT_SYMBOL_REQUIRED_MODULES:
        return None

    return CONTRACT_MODULE_ALLOWED_CONSUMERS.get(contract_module_key(target.name))


def contract_import_violations(
    source: SourceModule,
    target: ImportedModule,
    import_reference: ImportReference,
) -> list[str]:
    violations: list[str] = []
    location = format_source_location(source, import_reference.line_number)

    if source.context_code == SPECIAL_SOURCE_CONTRACTS:
        if target.kind == "bounded_context":
            violations.append(
                "Import de contexte metier interdit dans contracts: "
                f"module {source.module_name}, import {target.name}, ligne {location}."
            )
        if target.kind == "platform":
            violations.append(
                "Import de plateforme interdit dans contracts: "
                f"module {source.module_name}, import {target.name}, ligne {location}."
            )
        return violations

    if source.context_code == SPECIAL_SOURCE_PLATFORM:
        if target.kind == "bounded_context":
            if (
                source.module_name == ORCHESTRATOR_COMPOSITION_MODULE
                and target.name in ORCHESTRATOR_COMPOSITION_ALLOWED_IMPORTS
            ):
                return violations
            violations.append(
                "Import de contexte metier interdit dans platform: "
                f"module {source.module_name}, import {target.name}, ligne {location}."
            )
        return violations

    if target.kind != "contracts":
        return violations

    if len(import_reference.symbol_names) > 0:
        for symbol_name in import_reference.symbol_names:
            allowed_consumers = allowed_contract_consumers(target, symbol_name)
            if allowed_consumers is not None and source.context_code in allowed_consumers:
                continue

            violations.append(
                "Import de contrat publie interdit: "
                f"contexte {source.context_code}, module {source.module_name}, "
                f"import {format_import_reference(target, import_reference)}, symbole {symbol_name}, "
                f"ligne {location}."
            )
        return violations

    allowed_consumers = CONTRACT_MODULE_ALLOWED_CONSUMERS.get(contract_module_key(target.name))
    if allowed_consumers is None or source.context_code not in allowed_consumers:
        violations.append(
            "Import de contrat publie interdit: "
            f"contexte {source.context_code}, module {source.module_name}, "
            f"import {target.name}, ligne {location}."
        )

    return violations


def domain_layer_violations(
    source: SourceModule,
    target: ImportedModule,
    import_reference: ImportReference,
) -> list[str]:
    if source.layer != "domain":
        return []

    violations: list[str] = []
    location = format_source_location(source, import_reference.line_number)
    external_root = target.name.split(".", 1)[0]
    if target.kind == "external" and external_root in DOMAIN_FORBIDDEN_EXTERNAL_IMPORTS:
        violations.append(
            f"Import de framework externe interdit dans domain: contexte {source.context_code}, "
            f"module {source.module_name}, framework {external_root} "
            f"({DOMAIN_FORBIDDEN_EXTERNAL_IMPORTS[external_root]}), ligne {location}."
        )

    if target.kind == "platform":
        violations.append(
            f"Import de plateforme interdit dans domain: contexte {source.context_code}, "
            f"module {source.module_name}, import {target.name}, ligne {location}."
        )

    if target.kind == "bounded_context" and target.context_code == source.context_code:
        if target.layer == "adapters":
            violations.append(
                f"Import d'adapter interdit dans domain: contexte {source.context_code}, "
                f"module {source.module_name}, import {target.name}, ligne {location}."
            )
        if target.layer == "application":
            violations.append(
                f"Import de couche application interdit dans domain: contexte {source.context_code}, "
                f"module {source.module_name}, import {target.name}, ligne {location}."
            )

    return violations


def direct_qdrant_access_violations(
    source: SourceModule,
    target: ImportedModule,
    import_reference: ImportReference,
) -> list[str]:
    if source.context_code not in QDRANT_DIRECT_ACCESS_FORBIDDEN_CONSUMERS:
        return []
    if target.kind != "external":
        return []
    if target.name.split(".", 1)[0] != "qdrant_client":
        return []

    location = format_source_location(source, import_reference.line_number)
    return [
        "Accès direct à Qdrant interdit: "
        f"consommateur {source.context_code} ({source.module_name}), "
        f"import {format_import_reference(target, import_reference)}, ligne {location}."
    ]


def intercontext_violation(
    source: SourceModule,
    target: ImportedModule,
    relations: list[PublishedRelation],
    import_reference: ImportReference,
) -> str:
    contracts = expected_contracts(source.context_code, str(target.context_code), relations)
    location = format_source_location(source, import_reference.line_number)
    return (
        "Import intercontexte interdit: "
        f"consommateur {source.context_code} ({source.module_name}), "
        f"producteur {target.context_code} ({target.context_module}), "
        f"import {target.name}, contrat publié attendu: {contracts}, ligne {location}."
    )


def find_context_cycles(edges: set[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for source, target in edges:
        graph.setdefault(source, set()).add(target)
        graph.setdefault(target, set())

    cycles: list[list[str]] = []
    seen_signatures: set[tuple[str, ...]] = set()

    def canonical_cycle(cycle: list[str]) -> tuple[str, ...]:
        body = cycle[:-1]
        rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
        reversed_body = list(reversed(body))
        rotations.extend(tuple(reversed_body[index:] + reversed_body[:index]) for index in range(len(reversed_body)))
        canonical = min(rotations)
        return (*canonical, canonical[0])

    def visit(start: str, current: str, path: list[str], visiting: set[str]) -> None:
        for next_node in sorted(graph[current]):
            if next_node == start:
                cycle = [*path, start]
                signature = canonical_cycle(cycle)
                if signature not in seen_signatures:
                    seen_signatures.add(signature)
                    cycles.append(cycle)
                continue
            if next_node in visiting:
                continue
            if next_node not in graph:
                continue

            visit(start, next_node, [*path, next_node], {*visiting, next_node})

    for node in sorted(graph):
        visit(node, node, [node], {node})

    return cycles


def analyze_architecture(
    app_root: Path,
    contexts_by_module: dict[str, ContextDefinition],
    relations: list[PublishedRelation],
) -> tuple[list[str], int, int]:
    require_directory(app_root, "Racine app")
    validate_app_root_structure(app_root, contexts_by_module)

    violations: list[str] = []
    context_edges: set[tuple[str, str]] = set()
    analyzed_file_count = 0
    analyzed_import_count = 0

    for path in sorted(app_root.rglob("*.py")):
        source = classify_source_module(app_root, path, contexts_by_module)
        if source is None:
            relative_parts = path.relative_to(app_root).parts
            if relative_parts != ("__init__.py",):
                violations.append(f"Module app non déclaré dans le registre : {path.relative_to(REPOSITORY_ROOT)}.")
            continue

        analyzed_file_count += 1
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        violations.extend(find_domain_api_models(source, tree))

        for import_reference in imported_references(source, tree):
            analyzed_import_count += 1
            target = classify_import(import_reference.module_name, contexts_by_module)

            violations.extend(contract_import_violations(source, target, import_reference))

            if source.context_code in {SPECIAL_SOURCE_CONTRACTS, SPECIAL_SOURCE_PLATFORM}:
                continue

            if target.kind == "contracts":
                continue

            violations.extend(direct_qdrant_access_violations(source, target, import_reference))
            violations.extend(domain_layer_violations(source, target, import_reference))

            if target.kind != "bounded_context":
                continue

            if target.context_code == source.context_code:
                continue

            context_edges.add((source.context_code, str(target.context_code)))

            if allows_facade_import(source, target, relations):
                continue

            violations.append(intercontext_violation(source, target, relations, import_reference))

    for cycle in find_context_cycles(context_edges):
        violations.append(f"Cycle intercontexte interdit: {' -> '.join(cycle)}.")

    unique_violations = sorted(set(violations))
    return unique_violations, analyzed_file_count, analyzed_import_count


def main() -> int:
    try:
        args = parse_args()
        app_root = Path(args.app_root).resolve()
        context_registry_path = Path(args.context_registry_path).resolve()
        specification_path = Path(args.specification_path).resolve()
        require_path_under_repository(app_root, "app-root")
        require_path_under_repository(context_registry_path, "context-registry-path")
        require_path_under_repository(specification_path, "specification-path")

        _, contexts_by_module = load_context_definitions(context_registry_path)
        relations = load_published_relations(specification_path)
        validate_contract_consumer_rules(relations)
        violations, analyzed_file_count, analyzed_import_count = analyze_architecture(
            app_root=app_root,
            contexts_by_module=contexts_by_module,
            relations=relations,
        )
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"Erreur de configuration M-001: {exc}", file=sys.stderr)
        return 1

    if len(violations) > 0:
        print("Frontières d'import M-001 invalides:", file=sys.stderr)
        for violation in violations:
            print(f"- {violation}", file=sys.stderr)
        return 1

    print(
        "Frontières d'import M-001 valides: "
        f"{analyzed_file_count} fichier(s), {analyzed_import_count} import(s) contrôlé(s)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
