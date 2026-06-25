"""Points d'entrée techniques pour la stack Compose locale M-002."""

from __future__ import annotations

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


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
            payload = json.dumps(
                {"service": service_id, "status": "healthy"},
                ensure_ascii=False,
                sort_keys=True,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()


def _run_worker(*, service_id: str) -> None:
    _require_worker_service(service_id)
    threading.Event().wait()


def _require_worker_service(service_id: str) -> None:
    if service_id not in WORKER_SERVICE_IDS:
        raise ValueError(f"Worker local inconnu: {service_id}")


if __name__ == "__main__":
    raise SystemExit(main())
