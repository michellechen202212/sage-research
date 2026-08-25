"""Zero-dependency JSON HTTP API for commerce investigations."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit

from repository import InvestigationRepository, NotFoundError


def create_handler(repository: InvestigationRepository):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parts = [unquote(part) for part in urlsplit(self.path).path.split("/") if part]
            try:
                if parts == ["health"]:
                    self._send(200, {"status": "ok"})
                elif parts == ["customers"]:
                    self._send(200, {"customers": repository.list_customers()})
                elif len(parts) == 2 and parts[0] == "customers":
                    self._send(200, repository.customer(parts[1]))
                elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "activity":
                    self._send(200, repository.activity(parts[1]))
                elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "timeline":
                    self._send(200, {"customer_ref_id": parts[1], "events": repository.timeline(parts[1])})
                elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "returns":
                    self._send(200, {"customer_ref_id": parts[1], "returns": repository.returns(parts[1])})
                elif len(parts) == 2 and parts[0] == "orders":
                    self._send(200, repository.order(parts[1]))
                elif len(parts) == 2 and parts[0] == "receipts":
                    self._send(200, repository.receipt(parts[1]))
                else:
                    self._send(404, {"error": "route not found"})
            except NotFoundError:
                self._send(404, {"error": "entity not found"})

        def _send(self, status: int, payload: object) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the commerce investigation API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), create_handler(InvestigationRepository.from_fixtures()))
    print(f"Investigation API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
