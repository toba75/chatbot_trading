"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from app.contracts.identity import DomainIdentifier


HTTP_SERVICE_PORTS = {
    "ui": 8081,
    "orchestrator-api": 8080,
    "llm-gateway": 8090,
    "granite-docling": 8001,
    "embedding-service": 8101,
    "reranker-service": 8102,
    "backtest-engine": 8200,
}
WORKER_SERVICE_IDS = frozenset(("worker-documents", "worker-research", "worker-backtest"))
_M005_INDEX_PATH_PATTERN = re.compile(r"^/v1/documents/([^/]+)/index$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Runtime technique local M-002.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve-http")
    serve_parser.add_argument("service_id")
    serve_parser.add_argument("port", type=int)

    worker_parser = subparsers.add_parser("run-worker")
    worker_parser.add_argument("service_id")

    check_parser = subparsers.add_parser("check-worker")
    check_parser.add_argument("service_id")

    args = parser.parse_args()
    if args.command == "serve-http":
        _serve_http(service_id=args.service_id, port=args.port)
    if args.command == "run-worker":
        _run_worker(service_id=args.service_id)
    if args.command == "check-worker":
        _require_worker_service(args.service_id)
        return 0
    raise ValueError(f"Commande runtime locale inconnue: {args.command}")


def _serve_http(*, service_id: str, port: int) -> None:
    expected_port = HTTP_SERVICE_PORTS.get(service_id)
    if expected_port is None:
        raise ValueError(f"Service HTTP local inconnu: {service_id}")
    if port != expected_port:
        raise ValueError(f"Port HTTP local invalide pour {service_id}: {port}")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path not in {"/", "/health"}:
                self.send_response(404)
                self.end_headers()
                return
            _write_json_response(
                self,
                status_code=200,
                body={"service": service_id, "status": "healthy"},
            )

        def do_POST(self) -> None:
            body_result = _read_json_body(self)
            if body_result[0] != 200:
                _write_json_response(
                    self,
                    status_code=body_result[0],
                    body=body_result[1],
                )
                return
            status_code, response_body = _local_post_response(
                service_id=service_id,
                path=self.path,
                body=body_result[1],
            )
            _write_json_response(self, status_code=status_code, body=response_body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def _write_json_response(handler: BaseHTTPRequestHandler, *, status_code: int, body: dict[str, Any]) -> None:
    payload = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _read_json_body(handler: BaseHTTPRequestHandler) -> tuple[int, dict[str, Any]]:
    raw_length = handler.headers.get("Content-Length", "0")
    try:
        content_length = int(raw_length)
    except ValueError:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    if content_length < 0:
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "content_length"}
    if content_length == 0:
        return 200, {}
    raw_body = handler.rfile.read(content_length)
    try:
        parsed_body = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}
    if not isinstance(parsed_body, dict):
        return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "body"}
    return 200, parsed_body


def _local_post_response(*, service_id: str, path: str, body: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    if service_id != "orchestrator-api":
        return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}
    if path == "/v1/search":
        return 503, {
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/search",
        }
    index_match = _M005_INDEX_PATH_PATTERN.fullmatch(path)
    if index_match is not None:
        try:
            document_id = str(DomainIdentifier.parse_with_prefix(index_match.group(1), "DOC"))
        except ValueError:
            return 400, {"error_code": "HTTP_REQUEST_INVALID", "field": "document_id"}
        return 503, {
            "document_id": document_id,
            "error_code": "SERVICE_NOT_CONFIGURED",
            "endpoint": "POST /v1/documents/{document_id}/index",
        }
    return 404, {"error_code": "ENDPOINT_NOT_FOUND", "path": path}


def _run_worker(*, service_id: str) -> None:
    _require_worker_service(service_id)
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
