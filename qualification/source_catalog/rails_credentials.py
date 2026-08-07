"""Lecture ponctuelle des credentials Rails nécessaires au catalogue."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TIMEOUT = 60.0

# Le secret est produit par Rails sur stdout puis capturé par Python. Il ne
# figure jamais dans la ligne de commande, dans le catalogue ou dans un log.
_RUNNER_SCRIPT = (
    'require "json"; '
    'credentials = Rails.application.credentials.dig(:google_books); '
    'abort("google_books credentials absents") unless credentials.respond_to?(:[]); '
    'api_key = credentials[:api_key].to_s.strip; '
    'abort("google_books.api_key absent") if api_key.empty?; '
    'email = credentials[:email].to_s.strip; '
    'email = nil if email.empty?; '
    'puts JSON.generate({"api_key" => api_key, "email" => email})'
)


class RailsCredentialsUnavailable(RuntimeError):
    """Rails n'a pas pu fournir les credentials Google Books."""


@dataclass(frozen=True, slots=True)
class GoogleBooksCredentials:
    """Credentials extraits de Rails, conservés uniquement en mémoire."""

    api_key: str
    service_account_email: str | None = None


def _config_path(root: Path, configured: Path | None, default_name: str) -> Path:
    path = configured if configured is not None else root / default_name
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _parse_output(output: str) -> GoogleBooksCredentials:
    try:
        payload: Any = json.loads(output)
    except json.JSONDecodeError as error:
        raise RailsCredentialsUnavailable(
            "Rails a produit une réponse de credentials illisible"
        ) from error
    if not isinstance(payload, dict):
        raise RailsCredentialsUnavailable("Rails n'a pas produit un objet de credentials")

    api_key = payload.get("api_key")
    if not isinstance(api_key, str) or not api_key.strip():
        raise RailsCredentialsUnavailable("google_books.api_key est absent ou vide")
    email = payload.get("email")
    if email is not None and not isinstance(email, str):
        raise RailsCredentialsUnavailable("google_books.email doit être une chaîne")
    return GoogleBooksCredentials(
        api_key=api_key.strip(),
        service_account_email=email.strip() if email else None,
    )


def load_google_books_credentials(
    *,
    repo_root: Path = REPO_ROOT,
    compose_file: Path | None = None,
    env_file: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> GoogleBooksCredentials:
    """Demande à Rails les credentials Google Books sans déchiffrer Rails en Python.

    La commande est exécutée une seule fois par enrichissement. Sa sortie reste
    dans le pipe du processus ; seule la valeur normalisée est retournée à
    l'appelant.
    """
    if timeout <= 0:
        raise ValueError("Le délai de lecture des credentials doit être positif")
    root = repo_root.resolve()
    compose_path = _config_path(root, compose_file, "compose.rails.yaml")
    env_path = _config_path(root, env_file, ".env.rails")
    missing = [str(path) for path in (compose_path, env_path) if not path.is_file()]
    if missing:
        raise RailsCredentialsUnavailable(
            "Configuration Rails introuvable : " + ", ".join(missing)
        )

    command = [
        "docker",
        "compose",
        "--env-file",
        str(env_path),
        "-f",
        str(compose_path),
        "run",
        "--rm",
        "--no-deps",
        "web",
        "bundle",
        "exec",
        "rails",
        "runner",
        _RUNNER_SCRIPT,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            shell=False,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as error:
        raise RailsCredentialsUnavailable("Docker est introuvable") from error
    except subprocess.TimeoutExpired as error:
        raise RailsCredentialsUnavailable("Lecture des credentials Rails expirée") from error
    except OSError as error:
        raise RailsCredentialsUnavailable("Impossible d'exécuter Docker") from error

    if result.returncode != 0:
        # Ne jamais recopier stdout/stderr : une future modification de Rails
        # pourrait y faire apparaître une valeur confidentielle.
        raise RailsCredentialsUnavailable(
            f"Rails n'a pas fourni les credentials (code {result.returncode})"
        )
    return _parse_output(result.stdout.strip())
