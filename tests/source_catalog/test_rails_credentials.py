from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from qualification.source_catalog import rails_credentials
from qualification.source_catalog.rails_credentials import (
    RailsCredentialsUnavailable,
    load_google_books_credentials,
)


def _files(root: Path) -> None:
    (root / "compose.rails.yaml").write_text("services: {}\n", encoding="utf-8")
    (root / ".env.rails").write_text("SECRET_KEY_BASE=test\n", encoding="utf-8")


def test_lit_la_cle_et_l_email_sans_ajouter_le_secret_a_la_commande(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _files(tmp_path)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps({"api_key": "secret-test", "email": "sa@example.test"}), stderr="")

    monkeypatch.setattr(rails_credentials.subprocess, "run", run)

    credentials = load_google_books_credentials(repo_root=tmp_path)

    assert credentials.api_key == "secret-test"
    assert credentials.service_account_email == "sa@example.test"
    command, kwargs = calls[0]
    assert "secret-test" not in " ".join(command)
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == tmp_path


def test_l_email_est_optionnel(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _files(tmp_path)
    monkeypatch.setattr(
        rails_credentials.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"api_key": "secret-test", "email": None}), stderr=""
        ),
    )

    credentials = load_google_books_credentials(repo_root=tmp_path)

    assert credentials.service_account_email is None


def test_ne_rejoue_pas_une_commande_rails_en_echec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _files(tmp_path)
    monkeypatch.setattr(
        rails_credentials.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 1, stdout="secret-test", stderr="erreur"
        ),
    )

    with pytest.raises(RailsCredentialsUnavailable, match="code 1") as error:
        load_google_books_credentials(repo_root=tmp_path)

    assert "secret-test" not in str(error.value)


@pytest.mark.parametrize(
    "stdout, message",
    [
        ("not-json", "illisible"),
        (json.dumps({"api_key": ""}), "absent ou vide"),
        (json.dumps({"api_key": "secret-test", "email": 42}), "doit être une chaîne"),
    ],
)
def test_refuse_une_sortie_de_credentials_invalide(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout: str,
    message: str,
) -> None:
    _files(tmp_path)
    monkeypatch.setattr(
        rails_credentials.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 0, stdout=stdout, stderr=""),
    )

    with pytest.raises(RailsCredentialsUnavailable, match=message):
        load_google_books_credentials(repo_root=tmp_path)
