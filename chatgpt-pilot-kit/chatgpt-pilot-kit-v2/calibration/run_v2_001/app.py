"""Standard-library HTTP API for commerce investigations."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

from data_access import InvestigationRepository, NotFoundError, create_database


class InvestigationHandler(BaseHTTPRequestHandler):
    repository: InvestigationRepository

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        parts = [unquote(part) for part in parsed.path.strip("/").split("/") if part]
        query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
        try:
            if parts == ["health"]:
                self._json(200, {"status": "ok"})
            elif len(parts) == 2 and parts[0] == "customers":
                self._json(200, self.repository.customer_activity(parts[1]))
            elif len(parts) == 3 and parts[0] == "customers" and parts[2] == "timeline":
                self._json(200, self.repository.timeline(parts[1]))
            elif len(parts) == 2 and parts[0] == "orders":
                self._json(200, self.repository.order_detail(parts[1]))
            elif len(parts) == 2 and parts[0] == "payments":
                self._json(200, self.repository.payment_activity(parts[1]))
            elif len(parts) == 2 and parts[0] == "receipts":
                self._json(200, self.repository.receipt_detail(parts[1]))
            elif parts == ["receipts"]:
                allowed = {key: query.get(key) for key in ("customer_id", "location_id", "business_date", "sku", "tender_type")}
                self._json(200, self.repository.receipt_projection(**allowed))
            else:
                self._json(404, {"error": "route not found"})
        except NotFoundError as error:
            self._json(404, {"error": str(error)})
        except Exception:
            self._json(500, {"error": "internal server error"})

    def _json(self, status: int, body: object) -> None:
        encoded = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return


def make_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    handler = type("ConfiguredInvestigationHandler", (InvestigationHandler,), {})
    handler.repository = InvestigationRepository(create_database())
    return ThreadingHTTPServer((host, port), handler)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the commerce investigation API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = make_server(args.host, args.port)
    print(f"Investigation API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
