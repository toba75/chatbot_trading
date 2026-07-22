"""Construit la fixture réelle de qualification des environnements M-013."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pypdf import PdfReader, PdfWriter

from app.platform.development_e2e import (
    _EXPECTED_QUALIFICATION_ROUTES,
    _qualification_route_names,
)


_FIXTURE_RELATIVE_PATH = Path(
    "data/corpus/ostrading-environment-qualification-5-pages.pdf"
)
_MANIFEST_RELATIVE_PATH = Path(
    "docs/governance/m013_environment_qualification_fixture.json"
)


@dataclass(frozen=True, slots=True)
class QualificationPageSource:
    fixture_page_number: int
    source_path: str
    source_sha256: str
    source_page_number: int
    source_page_content_sha256: str
    expected_page_state: str
    expected_route_name: str
    expected_conversion_tool_name: str | None
    expected_fallback_triggering_error_code: str | None


_PAGE_SOURCES = (
    QualificationPageSource(
        fixture_page_number=1,
        source_path="data/corpus/the-original-turtle-trading-rules.pdf",
        source_sha256="073f361ebb4ac6c10765a21ba7cca42d75fde8fabadc84340e6bbfca444fbda4",
        source_page_number=3,
        source_page_content_sha256=(
            "4fa9c162f0766c8b1ce17e74a90137ac94876a7d67db3140f4619fa90f5754b7"
        ),
        expected_page_state="NATIVE_OK",
        expected_route_name="NATIVE_STANDARD",
        expected_conversion_tool_name="DOCLING_STANDARD",
        expected_fallback_triggering_error_code=None,
    ),
    QualificationPageSource(
        fixture_page_number=2,
        source_path="data/corpus/the-original-turtle-trading-rules.pdf",
        source_sha256="073f361ebb4ac6c10765a21ba7cca42d75fde8fabadc84340e6bbfca444fbda4",
        source_page_number=1,
        source_page_content_sha256=(
            "dfc383839186a3d6dcab33825678eac527b2f477028ce48357dac3330959a4f0"
        ),
        expected_page_state="MIXED_CONTENT",
        expected_route_name="MIXED_PAGEWISE",
        expected_conversion_tool_name="GRANITE_DOCLING",
        expected_fallback_triggering_error_code=None,
    ),
    QualificationPageSource(
        fixture_page_number=3,
        source_path="data/corpus/trading-on-momentum.pdf",
        source_sha256="6a77fd40209cbb1e988ef8674baf6dd1e410f9907a813566f7668e637c004b03",
        source_page_number=123,
        source_page_content_sha256=(
            "a7483f08e6a9aa11435aa62fb2a0788f584c101ce55bfc9d408f986e2bbcc294"
        ),
        expected_page_state="SCAN_DEGRADED",
        expected_route_name="PREPROCESS_GRANITE",
        expected_conversion_tool_name="GEMMA_VISION",
        expected_fallback_triggering_error_code="DOCLING_PROVENANCE_MISSING",
    ),
    QualificationPageSource(
        fixture_page_number=4,
        source_path=(
            "data/corpus/A Century of Profitable Industry Trends "
            "Carlo Zarattini Gary Antonacci.pdf"
        ),
        source_sha256="7a3001e2de57c3e028a5d36bbcfaa7fb773ae3b77a144aaefcd4cc221b1de03d",
        source_page_number=19,
        source_page_content_sha256=(
            "1a1e2883ac692a20b75709dbcf63fd3ef432c5bfb888e7ac7dc8cb9909dcccd2"
        ),
        expected_page_state="COMPLEX_VISUAL",
        expected_route_name="TARGETED_ENRICHMENT",
        expected_conversion_tool_name="DOCLING_STANDARD",
        expected_fallback_triggering_error_code=None,
    ),
    QualificationPageSource(
        fixture_page_number=5,
        source_path=(
            "data/corpus/dual-momentum-investing-an-innovative-strategy-for-higher-"
            "returns-with-lower-risk.pdf"
        ),
        source_sha256="8c536df8808f9e1988fa25795ee6774060cd8f0998d8ff5063f3c7ad16400475",
        source_page_number=2,
        source_page_content_sha256=(
            "cd6b970db6ec12f72e5928308170c8070c9751e40791db4237db18f2a6c1fa06"
        ),
        expected_page_state="EMPTY",
        expected_route_name="SKIP_EMPTY",
        expected_conversion_tool_name=None,
        expected_fallback_triggering_error_code=None,
    ),
)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _page_content_sha256(page: object) -> str:
    contents = page.get_contents()
    return sha256(b"" if contents is None else contents.get_data()).hexdigest()


def _build_pdf(repository_root: Path) -> bytes:
    writer = PdfWriter()
    for source in _PAGE_SOURCES:
        source_path = repository_root / source.source_path
        if _file_sha256(source_path) != source.source_sha256:
            raise ValueError(f"QUALIFICATION_SOURCE_SHA256_MISMATCH: {source.source_path}")
        reader = PdfReader(str(source_path), strict=True)
        page = reader.pages[source.source_page_number - 1]
        if _page_content_sha256(page) != source.source_page_content_sha256:
            raise ValueError(
                f"QUALIFICATION_SOURCE_PAGE_SHA256_MISMATCH: {source.source_path}"
            )
        writer.add_page(page)
    writer.add_metadata(
        {
            "/OSTradingFixtureId": "M013-ENVIRONMENT-QUALIFICATION-5-PAGES-V1",
            "/OSTradingFixtureSchemaVersion": "1.0",
        }
    )
    stream = BytesIO()
    writer.write(stream)
    return stream.getvalue()


def _write_new_or_identical(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f"QUALIFICATION_GENERATED_ARTIFACT_DIFFERS: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    fixture_bytes = _build_pdf(repository_root)
    fixture_path = repository_root / _FIXTURE_RELATIVE_PATH
    with TemporaryDirectory(prefix="ost_m013_fixture_") as directory:
        temporary_fixture = Path(directory) / _FIXTURE_RELATIVE_PATH.name
        temporary_fixture.write_bytes(fixture_bytes)
        observed_routes = _qualification_route_names(temporary_fixture)
    if observed_routes != _EXPECTED_QUALIFICATION_ROUTES:
        raise ValueError(
            "QUALIFICATION_ROUTE_MISMATCH: " + ",".join(observed_routes)
        )

    manifest = {
        "schema_version": "1.0",
        "fixture_path": _FIXTURE_RELATIVE_PATH.as_posix(),
        "fixture_sha256": sha256(fixture_bytes).hexdigest(),
        "routing_policy_version": "routing-v1",
        "pages": [asdict(source) for source in _PAGE_SOURCES],
    }
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_new_or_identical(fixture_path, fixture_bytes)
    _write_new_or_identical(repository_root / _MANIFEST_RELATIVE_PATH, manifest_bytes)
    print(manifest["fixture_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
