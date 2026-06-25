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
class PublishedRelation:
    relation_source: str
    relation_target: str
    producer: str
    consumer: str
    contract: str
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
                relation_type=row["Type"],
            )
        )

    return relations


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


def imported_module_names(source: SourceModule, tree: ast.AST) -> list[str]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module_name = resolve_import_from_module(source, node)
            if module_name:
                imports.append(module_name)
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
        for relation in related_relations(source.context_code, str(target.context_code), relations)
    )


def domain_layer_violations(source: SourceModule, target: ImportedModule) -> list[str]:
    if source.layer != "domain":
        return []

    violations: list[str] = []
    external_root = target.name.split(".", 1)[0]
    if target.kind == "external" and external_root in DOMAIN_FORBIDDEN_EXTERNAL_IMPORTS:
        violations.append(
            f"Import de framework externe interdit dans domain: contexte {source.context_code}, "
            f"module {source.module_name}, framework {external_root} "
            f"({DOMAIN_FORBIDDEN_EXTERNAL_IMPORTS[external_root]})."
        )

    if target.kind == "platform":
        violations.append(
            f"Import de plateforme interdit dans domain: contexte {source.context_code}, "
            f"module {source.module_name}, import {target.name}."
        )

    if target.kind == "bounded_context" and target.context_code == source.context_code:
        if target.layer == "adapters":
            violations.append(
                f"Import d'adapter interdit dans domain: contexte {source.context_code}, "
                f"module {source.module_name}, import {target.name}."
            )
        if target.layer == "application":
            violations.append(
                f"Import de couche application interdit dans domain: contexte {source.context_code}, "
                f"module {source.module_name}, import {target.name}."
            )

    return violations


def intercontext_violation(
    source: SourceModule,
    target: ImportedModule,
    relations: list[PublishedRelation],
) -> str:
    contracts = expected_contracts(source.context_code, str(target.context_code), relations)
    return (
        "Import intercontexte interdit: "
        f"consommateur {source.context_code} ({source.module_name}), "
        f"producteur {target.context_code} ({target.context_module}), "
        f"import {target.name}, contrat publié attendu: {contracts}."
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

    violations: list[str] = []
    context_edges: set[tuple[str, str]] = set()
    analyzed_file_count = 0
    analyzed_import_count = 0

    for path in sorted(app_root.rglob("*.py")):
        source = classify_source_module(app_root, path, contexts_by_module)
        if source is None:
            continue

        analyzed_file_count += 1
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        violations.extend(find_domain_api_models(source, tree))

        for import_name in imported_module_names(source, tree):
            analyzed_import_count += 1
            target = classify_import(import_name, contexts_by_module)

            if target.kind == "contracts":
                continue

            violations.extend(domain_layer_violations(source, target))

            if target.kind != "bounded_context":
                continue

            if target.context_code == source.context_code:
                continue

            context_edges.add((source.context_code, str(target.context_code)))

            if allows_facade_import(source, target, relations):
                continue

            violations.append(intercontext_violation(source, target, relations))

    for cycle in find_context_cycles(context_edges):
        violations.append(f"Cycle intercontexte interdit: {' -> '.join(cycle)}.")

    unique_violations = sorted(set(violations))
    return unique_violations, analyzed_file_count, analyzed_import_count


def main() -> int:
    args = parse_args()
    app_root = Path(args.app_root).resolve()
    context_registry_path = Path(args.context_registry_path).resolve()
    specification_path = Path(args.specification_path).resolve()

    _, contexts_by_module = load_context_definitions(context_registry_path)
    relations = load_published_relations(specification_path)
    violations, analyzed_file_count, analyzed_import_count = analyze_architecture(
        app_root=app_root,
        contexts_by_module=contexts_by_module,
        relations=relations,
    )

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
