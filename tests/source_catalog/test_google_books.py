from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from qualification.source_catalog.google_books import (
    GoogleBooksClient,
    InvalidProviderResponse,
    ProviderUnavailable,
    classify_resolution,
    normalize_volume,
    _canonical_isbn,
)


def _volume(identifier: str, title: str = "Advances in Financial Machine Learning") -> dict:
    return {
        "id": identifier,
        "volumeInfo": {
            "title": title,
            "authors": ["Marcos Lopez de Prado"],
            "publishedDate": "2018",
            "industryIdentifiers": [{"type": "ISBN_13", "identifier": "9781119482086"}],
            "averageRating": 4.5,
            "ratingsCount": 20,
        },
    }


def test_resout_un_isbn_exact() -> None:
    def transport(url: str, timeout: float) -> dict:
        assert timeout == 2
        assert parse_qs(urlparse(url).query)["q"] == ["isbn:9781119482086"]
        return {"items": [_volume("v1")]}

    result = GoogleBooksClient(timeout=2, transport=transport).resolve(
        isbns=["9781119482086"], title="Advances in Financial Machine Learning", authors=[]
    )

    assert result["method"] == "isbn"
    assert result["candidates"][0]["candidate_id"] == "google_books:v1"
    assert classify_resolution(result, title="Advances in Financial Machine Learning")[0] == "accepted"


def test_conserve_l_ambiguite_titre_auteur() -> None:
    def transport(url: str, timeout: float) -> dict:
        return {"items": [_volume("v1"), _volume("v2")]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[], title="Advances in Financial Machine Learning", authors=["Marcos"]
    )

    status, candidates = classify_resolution(result, title="Advances in Financial Machine Learning")
    assert status == "ambiguous"
    assert {candidate["status"] for candidate in candidates} == {"ambiguous"}


def test_volume_absent_est_un_no_match() -> None:
    client = GoogleBooksClient(transport=lambda url, timeout: {"totalItems": 0, "items": []})

    result = client.resolve(isbns=[], title="publication introuvable", authors=[])

    assert classify_resolution(result, title="publication introuvable")[0] == "no_match"


def test_reponse_invalide_est_observable() -> None:
    client = GoogleBooksClient(transport=lambda url, timeout: {"items": {}})

    with pytest.raises(InvalidProviderResponse):
        client.resolve(isbns=[], title="titre", authors=[])


def test_la_cle_est_envoyee_mais_absente_de_l_observation() -> None:
    observed: dict[str, str] = {}

    def transport(url: str, timeout: float) -> dict:
        observed["url"] = url
        assert parse_qs(urlparse(url).query)["key"] == ["secret-test"]
        return {"items": []}

    result = GoogleBooksClient(api_key="secret-test", transport=transport).resolve(
        isbns=[], title="publication introuvable", authors=[]
    )

    assert "secret-test" not in result["attempts"][0]["url"]
    assert "secret-test" in observed["url"]


def test_isbn_exact_mais_titre_incoherent_est_rejete() -> None:
    def transport(url: str, timeout: float) -> dict:
        return {"items": [_volume("v1", title="Ouvrage sans rapport")]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=["9781119482086"], title="Advances in Financial Machine Learning", authors=[]
    )

    assert result["method"] == "isbn_conflict"
    assert classify_resolution(result, title="Advances in Financial Machine Learning")[0] == "rejected"


def test_fournisseur_indisponible_ne_devient_pas_un_no_match() -> None:
    def unavailable(url: str, timeout: float) -> dict:
        raise ProviderUnavailable("429")

    with pytest.raises(ProviderUnavailable):
        GoogleBooksClient(transport=unavailable).resolve(isbns=[], title="titre", authors=[])


def test_note_incomplete_refusee() -> None:
    volume = _volume("v1")
    del volume["volumeInfo"]["ratingsCount"]

    candidate = normalize_volume(volume, "2026-08-07T00:00:00+00:00")

    assert candidate["rating"] is None


def test_consulte_tous_les_isbn_et_fusionne_les_volumes() -> None:
    queries: list[str] = []

    def transport(url: str, timeout: float) -> dict:
        query = parse_qs(urlparse(url).query)["q"][0]
        queries.append(query)
        identifier = "v1" if query.endswith("1119482086") else "v2"
        isbn = "9781119482086" if identifier == "v1" else "9780307720788"
        item = _volume(identifier)
        item["volumeInfo"]["industryIdentifiers"] = [{"type": "ISBN_13", "identifier": isbn}]
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=["9781119482086", "9780307720788"],
        title="Advances in Financial Machine Learning",
        authors=[],
    )

    assert queries == ["isbn:9781119482086", "isbn:9780307720788"]
    assert {candidate["volume_id"] for candidate in result["candidates"]} == {"v1", "v2"}


def test_utilise_tous_les_auteurs_editeur_et_annee_pour_classer() -> None:
    queries: list[str] = []

    def transport(url: str, timeout: float) -> dict:
        query = parse_qs(urlparse(url).query)["q"][0]
        queries.append(query)
        if "inauthor:Carlo Zarattini" in query:
            item = _volume("strong", "A Century of Profitable Industry Trends")
            item["volumeInfo"].update({"authors": ["Carlo Zarattini"], "publisher": "Wiley"})
            return {"items": [item]}
        item = _volume("weak", "A Century of Profitable Industry")
        item["volumeInfo"].update({"authors": ["Carlo Zarattini"], "publisher": "Other Press"})
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[],
        title="A Century of Profitable Industry Trends",
        title_variants=["A Century of Profitable Industry Trends"],
        authors=["Carlo Zarattini", "Gary Antonacci"],
        publisher="Wiley",
        publication_year="2018",
    )
    status, candidates = classify_resolution(
        result,
        title="A Century of Profitable Industry Trends",
        authors=["Carlo Zarattini", "Gary Antonacci"],
        publisher="Wiley",
        publication_year="2018",
    )

    assert "intitle:A Century of Profitable Industry Trends inauthor:Carlo Zarattini" in queries
    assert "intitle:A Century of Profitable Industry Trends inauthor:Gary Antonacci" in queries
    assert "intitle:A Century of Profitable Industry Trends inpublisher:Wiley" in queries
    assert candidates[0]["volume_id"] == "strong"
    assert candidates[0]["matching"]["score"] > candidates[1]["matching"]["score"]
    assert status == "ambiguous"


def test_fusionne_les_champs_d_un_volume_retrouve_par_deux_requetes() -> None:
    calls = 0

    def transport(url: str, timeout: float) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            return {"items": [{"id": "same", "volumeInfo": {"title": "Causal Factor Investing"}}]}
        item = _volume("same", "Causal Factor Investing")
        item["volumeInfo"].update({"publisher": "Cambridge University Press"})
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[],
        title="Causal Factor Investing",
        authors=["Marcos M. Lopez de Prado"],
        publisher="Cambridge University Press",
        publication_year="2023",
    )
    status, candidates = classify_resolution(
        result,
        title="Causal Factor Investing",
        authors=["Marcos M. Lopez de Prado"],
        publisher="Cambridge University Press",
        publication_year="2023",
    )

    assert status == "candidate"
    assert candidates[0]["authors"] == ["Marcos Lopez de Prado"]
    assert candidates[0]["publisher"] == "Cambridge University Press"
    assert candidates[0]["matching"]["score"] >= 0.72


def test_ne_traite_pas_un_resultat_titre_comme_preuve_issn() -> None:
    def transport(url: str, timeout: float) -> dict:
        item = _volume("magazine", "Revue quantitative")
        item["volumeInfo"]["industryIdentifiers"] = []
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[], issns=["20493630"], title="Revue quantitative", authors=[]
    )

    assert result["method"] == "title_author"


def test_accepte_un_issn_exact_et_coherent() -> None:
    def transport(url: str, timeout: float) -> dict:
        item = _volume("magazine", "Revue quantitative")
        item["volumeInfo"]["industryIdentifiers"] = [{"type": "ISSN", "identifier": "20493630"}]
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[], issns=["20493630"], title="Revue quantitative", authors=[]
    )

    assert classify_resolution(result, title="Revue quantitative")[0] == "accepted"


def test_ne_promeut_pas_un_issn_exact_mais_un_titre_contradictoire() -> None:
    def transport(url: str, timeout: float) -> dict:
        item = _volume("wrong-magazine", "Unrelated title")
        item["volumeInfo"]["industryIdentifiers"] = [{"type": "ISSN", "identifier": "20493630"}]
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=[], issns=["20493630"], title="Revue quantitative", authors=[]
    )

    assert classify_resolution(result, title="Revue quantitative")[0] == "rejected"


def test_ne_convertit_pas_un_isbn_979_en_isbn10() -> None:
    def transport(url: str, timeout: float) -> dict:
        item = _volume("wrong-edition", "Target")
        item["volumeInfo"]["industryIdentifiers"] = [{"type": "ISBN_10", "identifier": "123456789X"}]
        return {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=["9791234567896"], title="Target", authors=[]
    )

    assert result["method"] == "title_author"
    assert classify_resolution(result, title="Target")[0] == "candidate"


def test_tolere_un_bloc_d_identifiants_absent() -> None:
    def transport(url: str, timeout: float) -> dict:
        return {"items": [{"id": "no-identifiers", "volumeInfo": {"title": "Target", "industryIdentifiers": None}}]}

    result = GoogleBooksClient(transport=transport).resolve(isbns=[], title="Target", authors=[])

    assert result["candidates"][0]["identifiers"] == {"isbn10": [], "isbn13": [], "issn": []}


def test_refuse_un_isbn10_avec_x_hors_du_chiffre_de_controle() -> None:
    assert _canonical_isbn("X123456788") is None


def test_omet_une_note_hors_limites() -> None:
    volume = _volume("bad-rating")
    volume["volumeInfo"].update({"averageRating": 6, "ratingsCount": -1})

    assert normalize_volume(volume, "2026-08-07T00:00:00+00:00")["rating"] is None


def test_ignore_les_auteurs_non_textuels_du_fournisseur() -> None:
    volume = _volume("bad-author", "Other")
    volume["volumeInfo"]["authors"] = [123]

    result = GoogleBooksClient(transport=lambda url, timeout: {"items": [volume]}).resolve(
        isbns=[], title="Target", authors=["Author"]
    )

    assert result["candidates"][0]["authors"] == []


def test_reconnait_un_isbn_trouve_apres_le_fallback_titre() -> None:
    def transport(url: str, timeout: float) -> dict:
        query = parse_qs(urlparse(url).query)["q"][0]
        item = _volume("fallback", "Advances in Financial Machine Learning")
        return {"items": []} if query.startswith("isbn:") else {"items": [item]}

    result = GoogleBooksClient(transport=transport).resolve(
        isbns=["9781119482086"], title="Advances in Financial Machine Learning", authors=[]
    )

    assert result["method"] == "isbn"
    assert classify_resolution(result, title="Advances in Financial Machine Learning")[0] == "accepted"
