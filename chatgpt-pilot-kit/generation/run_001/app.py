"""HTTP JSON API for investigating the supplied synthetic commerce data."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from data_access import CommerceRepository, NotFoundError


class InvestigationAPI:
    def __init__(self, repository: CommerceRepository):
        self.repository = repository

    def route(self, method: str, path: str) -> tuple[int, dict | list]:
        if method != "GET":
            return 405, {"error": "method not allowed"}
        parts = [unquote(part) for part in path.strip("/").split("/") if part]
        try:
            if parts == ["health"]:
                return 200, {"status": "ok"}
            if parts == ["customers"]:
                return 200, self.repository.list_customers()
            if len(parts) == 2 and parts[0] == "customers":
                return 200, self.repository.customer(parts[1])
            if len(parts) == 3 and parts[0] == "customers" and parts[2] == "timeline":
                return 200, self.repository.timeline(parts[1])
            if len(parts) == 2 and parts[0] == "orders":
                return 200, self.repository.order(parts[1])
            if len(parts) == 2 and parts[0] == "receipts":
                return 200, self.repository.receipt(parts[1])
            return 404, {"error": "route not found"}
        except NotFoundError as exc:
            return 404, {"error": str(exc)}


def make_handler(api: InvestigationAPI):
    class Handler(BaseHTTPRequestHandler):
        def _respond(self) -> None:
            status, payload = api.route(self.command, urlparse(self.path).path)
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = _respond
        do_POST = _respond
        do_PUT = _respond
        do_DELETE = _respond

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the commerce investigation API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    api = InvestigationAPI(CommerceRepository.from_fixtures())
    server = ThreadingHTTPServer((args.host, args.port), make_handler(api))
    print(f"Listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
