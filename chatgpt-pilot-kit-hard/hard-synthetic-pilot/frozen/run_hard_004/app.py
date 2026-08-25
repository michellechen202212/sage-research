"""Minimal HTTP adapter for InvestigationService (Python standard library only)."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from investigation_service import InvestigationService, NotFoundError, initialize_database


class Handler(BaseHTTPRequestHandler):
    service: InvestigationService

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        try:
            if len(parts) == 3 and parts[:2] == ["v1", "orders"]:
                body = self.service.order(parts[2])
            elif len(parts) == 3 and parts[:2] == ["v1", "payments"]:
                body = self.service.payment(parts[2])
            elif len(parts) == 3 and parts[:2] == ["v1", "receipts"]:
                body = self.service.receipt(parts[2])
            elif len(parts) == 4 and parts[:2] == ["v1", "customers"] and parts[3] == "investigation":
                body = self.service.customer(parts[2])
            elif parts == ["v1", "compact"]:
                query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
                unknown = set(query) - {"customer_id", "record_type", "order_id", "sku", "from_at", "to_at"}
                if unknown:
                    raise ValueError("unknown filters: " + ", ".join(sorted(unknown)))
                body = self.service.compact(**query)
            else:
                raise NotFoundError("route", parsed.path)
            self._json(200, body)
        except NotFoundError as error:
            self._json(404, error.as_dict())
        except ValueError as error:
            self._json(400, {"error": "invalid_request", "message": str(error)})

    def _json(self, status, value):
        payload = json.dumps(value, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        return


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init-db")
    init.add_argument("database")
    init.add_argument("--schema", default="schema.sql")
    init.add_argument("--seed", default="seed.sql")
    serve = sub.add_parser("serve")
    serve.add_argument("database")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.command == "init-db":
        initialize_database(args.database, args.schema, args.seed)
        print(f"initialized {Path(args.database)}")
    else:
        Handler.service = InvestigationService(args.database)
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        print(f"serving http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
