from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


FORBIDDEN_EXACT_KEYS = frozenset(
    {
        "API_PORT",
        "BACKTEST_ENGINE_URL",
        "BACKTEST_WORKDIR",
        "DATABASE_URL",
        "EMBEDDING_MODEL_PATH",
        "EMBEDDING_SERVICE_URL",
        "GEMMA_API_KEY_FILE",
        "GEMMA_AUTH_MODE",
        "GEMMA_BASE_URL",
        "GEMMA_CA_BUNDLE",
        "GEMMA_CIRCUIT_BREAKER_FAILURE_THRESHOLD",
        "GEMMA_CIRCUIT_BREAKER_OPEN_SECONDS",
        "GEMMA_MODEL",
        "GEMMA_MODEL_REVISION",
        "GEMMA_RETRY_BEFORE_FIRST_TOKEN",
        "GEMMA_RUNTIME_VERSION",
        "GEMMA_TIMEOUT_SECONDS",
        "GEMMA_TLS_MODE",
        "GRANITE_MODEL_PATH",
        "GRANITE_URL",
        "LLM_GATEWAY_PORT",
        "LLM_GATEWAY_URL",
        "QDRANT_URL",
        "RERANKER_MODEL_PATH",
        "RERANKER_SERVICE_URL",
        "SPARK_ALLOWED_CLIENT_CIDRS",
        "UI_API_URL",
    }
)
FORBIDDEN_PREFIXES = ("GEMMA_",)
ALLOWED_SHELL_ENVIRONMENT_KEYS = frozenset({"PYTHONIOENCODING"})
ALLOWED_COMPOSE_ENVIRONMENT_BY_SERVICE = {
    "edge-gateway": frozenset({"CADDY_ADMIN"}),
    "postgres": frozenset({"POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD_FILE"}),
}
HISTORICAL_REGISTRY_PATHS = frozenset(
    {
        "app/platform/configuration/__init__.py",
        "app/platform/local_compose.py",
        "app/platform/security/network_boundary.py",
    }
)
M13_SECRET_SCANNER_PATHS = frozenset(
    {
        "scripts/validate_m013_acceptance.ps1",
        "scripts/validate_m013_backup_restore.ps1",
        "scripts/validate_m013_monitoring.ps1",
        "scripts/validate_m013_runbooks.ps1",
        "scripts/validate_m013_security.ps1",
    }
)
IGNORED_EXACT_PATHS = frozenset(
    {
        "scripts/validate_m013_config_environment.ps1",
        "scripts/validate_m013_config_environment.py",
    }
)
CODE_ENV_PATTERN = re.compile(r"\$(?:env:|Env:)([A-Za-z_][A-Za-z0-9_]*)")
CODE_BRACED_ENV_PATTERN = re.compile(r"\$\{(?:env:|Env:)([A-Za-z_][A-Za-z0-9_]*)\}")
CODE_PROVIDER_ENV_PATTERN = re.compile(r"(?<![$\{])\bEnv:([A-Za-z_][A-Za-z0-9_]*)")
CODE_DOTNET_ENV_PATTERN = re.compile(
    r"\[Environment\]::GetEnvironmentVariable\(\s*['\"]([A-Za-z_][A-Za-z0-9_]*)['\"]\s*\)"
)
OST_RECURSION_GUARD_PATTERN = re.compile(r"^OST_M\d{3}_PRECONDITION_ACCEPTANCE_RUNNING$")
COMPOSE_ENVIRONMENT_KEY_PATTERN = re.compile(r"^\s{6}([A-Za-z_][A-Za-z0-9_]*)\s*:")
COMPOSE_ENVIRONMENT_LIST_KEY_PATTERN = re.compile(r"^\s{6}-\s*([A-Za-z_][A-Za-z0-9_]*)=")
SERVICE_PATTERN = re.compile(r"^  ([A-Za-z0-9_.-]+):\s*$")
TOP_LEVEL_PATTERN = re.compile(r"^([A-Za-z][^:\s]*):\s*$")


class EnvironmentScanner:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.violations: list[str] = []
        self.exception_count = 0
        self.scanned_file_count = 0

    def relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def add_violation(self, path: str, line_number: int, message: str) -> None:
        self.violations.append(f"CONFIG_ENV_INPUT_REJECTED {path}:{line_number} {message}")

    def ignored_path(self, relative_path: str) -> bool:
        parts = relative_path.split("/")
        if any(part in {".git", ".tmp", "__pycache__"} for part in parts):
            return True
        return (
            relative_path in IGNORED_EXACT_PATHS
            or relative_path.startswith("tests/")
            or relative_path.startswith("docs/specs/")
            or relative_path.startswith("docs/tasks/milestone_013-config/")
        )

    def file_in_scope(self, relative_path: str) -> bool:
        if self.ignored_path(relative_path):
            return False
        if Path(relative_path).name == ".env":
            return True
        if relative_path.startswith("app/"):
            return relative_path.endswith((".py", ".js", ".ts"))
        if relative_path.startswith("scripts/"):
            return relative_path.endswith((".ps1", ".psm1", ".py", ".js", ".ts"))
        if relative_path.startswith("deploy/"):
            return relative_path.endswith((".yaml", ".yml", ".md"))
        if relative_path.startswith("docs/runbooks/"):
            return relative_path.endswith(".md")
        return False

    def scannable_files(self) -> list[Path]:
        files: list[Path] = []
        for relative_root in ("app", "scripts", "deploy", "docs/runbooks"):
            search_root = self.root / relative_root
            if not search_root.is_dir():
                continue
            for path in search_root.rglob("*"):
                if not path.is_file():
                    continue
                relative_path = self.relative_path(path)
                if self.file_in_scope(relative_path):
                    files.append(path)

        root_env = self.root / ".env"
        if root_env.is_file():
            files.append(root_env)
        return sorted(files)

    def forbidden_key_from_text(self, text: str) -> str | None:
        for key in FORBIDDEN_EXACT_KEYS:
            if key in text:
                return key
        for prefix in FORBIDDEN_PREFIXES:
            index = text.find(prefix)
            if index >= 0:
                end = index + len(prefix)
                while end < len(text) and (text[end].isdigit() or text[end] == "_" or "A" <= text[end] <= "Z"):
                    end += 1
                return text[index:end]
        return None

    def forbidden_environment_name(self, name: str) -> str | None:
        if name in FORBIDDEN_EXACT_KEYS:
            return name
        for prefix in FORBIDDEN_PREFIXES:
            if name.startswith(prefix):
                return name
        return None

    def historical_mention_allowed(self, relative_path: str, line: str, key: str) -> bool:
        if relative_path in HISTORICAL_REGISTRY_PATHS:
            self.exception_count += 1
            return True
        if relative_path == "docs/runbooks/configuration_applicative.md" and (
            "Migr" in line or "refus" in line or "interdit" in line or "rejet" in line
        ):
            self.exception_count += 1
            return True
        if relative_path == "app/platform/topology.py" and key == "GEMMA_VLLM_SERVICE_ID":
            self.exception_count += 1
            return True
        if relative_path in M13_SECRET_SCANNER_PATHS and (
            r"GEMMA_API_KEY\s*=" in line or r"VLLM_API_KEY\s*=" in line
        ):
            self.exception_count += 1
            return True
        return False

    def scan_environment_snapshot(self) -> None:
        for name in os.environ:
            forbidden_name = self.forbidden_environment_name(name)
            if forbidden_name is not None:
                self.add_violation("<process-env>", 1, f"variable homonyme shell interdite: {name}")

    def scan_code_environment_api(self, relative_path: str, line_number: int, line: str) -> None:
        if "os.environ" in line:
            if relative_path == "app/platform/local_runtime.py" and re.search(
                r"environment_snapshot\s*=\s*dict\(os\.environ\)", line
            ):
                self.exception_count += 1
            else:
                self.add_violation(
                    relative_path,
                    line_number,
                    "lecture os.environ interdite comme source applicative",
                )
        if "getenv(" in line or "os.getenv" in line:
            self.add_violation(relative_path, line_number, "lecture getenv interdite comme source applicative")
        if "process.env" in line:
            self.add_violation(relative_path, line_number, "lecture process.env interdite comme source applicative")

        for pattern, label in (
            (CODE_BRACED_ENV_PATTERN, "${env:...}"),
            (CODE_ENV_PATTERN, "$env:..."),
            (CODE_PROVIDER_ENV_PATTERN, "Env:"),
            (CODE_DOTNET_ENV_PATTERN, "[Environment]::GetEnvironmentVariable"),
        ):
            for match in pattern.finditer(line):
                name = match.group(1)
                self.add_shell_environment_violation(relative_path, line_number, name, label)

    def add_shell_environment_violation(
        self,
        relative_path: str,
        line_number: int,
        name: str,
        syntax_label: str,
    ) -> None:
        if name in ALLOWED_SHELL_ENVIRONMENT_KEYS or OST_RECURSION_GUARD_PATTERN.fullmatch(name) is not None:
            self.exception_count += 1
            return
        self.add_violation(
            relative_path,
            line_number,
            f"lecture {syntax_label} {name} interdite comme source applicative",
        )

    def scan_forbidden_key_line(self, relative_path: str, line_number: int, line: str) -> None:
        key = self.forbidden_key_from_text(line)
        if key is None:
            return
        if self.historical_mention_allowed(relative_path, line, key):
            return
        self.add_violation(relative_path, line_number, f"clé applicative historique interdite: {key}")

    def scan_documentation_line(self, relative_path: str, line_number: int, line: str) -> None:
        normalized = line.lower()
        if ".env" in normalized and "interdit" not in normalized and "ne doit" not in normalized:
            self.add_violation(relative_path, line_number, "référence .env opérationnelle interdite")
        for token in ("env_file", "environment:"):
            if token in normalized and "interdit" not in normalized and "ne doit" not in normalized:
                self.add_violation(relative_path, line_number, f"référence {token} opérationnelle interdite")

    def scan_compose_file(self, relative_path: str, lines: list[str]) -> None:
        current_service: str | None = None
        inside_services = False
        inside_environment = False

        for index, line in enumerate(lines, start=1):
            if line.strip() == "services:":
                inside_services = True
                current_service = None
                inside_environment = False
                continue

            if inside_services and TOP_LEVEL_PATTERN.match(line):
                inside_services = False
                current_service = None
                inside_environment = False
                continue

            service_match = SERVICE_PATTERN.match(line)
            if inside_services and service_match is not None:
                current_service = service_match.group(1)
                inside_environment = False
                continue

            if inside_services and re.match(r"^    env_file\s*:", line):
                self.add_violation(relative_path, index, f"env_file Compose interdit pour service {current_service}")

            if inside_services and re.match(r"^    environment\s*:", line):
                inside_environment = True
                continue

            if inside_environment and re.match(r"^    [A-Za-z0-9_-]+:", line):
                inside_environment = False

            if not inside_environment:
                continue

            key_match = COMPOSE_ENVIRONMENT_KEY_PATTERN.match(line) or COMPOSE_ENVIRONMENT_LIST_KEY_PATTERN.match(line)
            if key_match is None:
                continue

            key = key_match.group(1)
            allowed_keys = ALLOWED_COMPOSE_ENVIRONMENT_BY_SERVICE.get(current_service or "", frozenset())
            if key not in allowed_keys:
                self.add_violation(
                    relative_path,
                    index,
                    f"environment Compose non allowlisté pour service {current_service}: {key}",
                )
            elif self.forbidden_key_from_text(key) is not None:
                self.add_violation(
                    relative_path,
                    index,
                    f"environment Compose applicatif interdit pour service {current_service}: {key}",
                )
            else:
                self.exception_count += 1

    def scan_file(self, path: Path) -> None:
        relative_path = self.relative_path(path)
        self.scanned_file_count += 1

        if path.name == ".env":
            self.add_violation(relative_path, 1, "fichier .env interdit")
            return

        lines = path.read_text(encoding="utf-8-sig").splitlines()
        if relative_path.startswith("deploy/") and relative_path.endswith((".yaml", ".yml")):
            self.scan_compose_file(relative_path, lines)

        for index, line in enumerate(lines, start=1):
            self.scan_code_environment_api(relative_path, index, line)
            self.scan_forbidden_key_line(relative_path, index, line)
            if relative_path.startswith("docs/runbooks/") or relative_path == "deploy/local-compose/README.md":
                self.scan_documentation_line(relative_path, index, line)

    def run(self) -> int:
        self.scan_environment_snapshot()
        for path in self.scannable_files():
            self.scan_file(path)

        if self.violations:
            for violation in self.violations:
                print(violation)
            return 1

        print(
            "Gate environnement M13-config GREEN: "
            f"{self.scanned_file_count} fichier(s), "
            f"{self.exception_count} exception(s) technique(s) contrôlée(s)."
        )
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Gate M13-config contre les entrées environnement applicatives.")
    parser.add_argument("--root", required=True)
    args = parser.parse_args()

    scanner = EnvironmentScanner(Path(args.root))
    return scanner.run()


if __name__ == "__main__":
    raise SystemExit(main())
