"""Dependency-free JSON HTTP API for commerce investigations."""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from repository import InvestigationRepository, NotFoundError, initialize_database


def create_handler(database_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: object) -> None:
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            parts = [unquote(p) for p in urlparse(self.path).path.split("/") if p]
            try:
                with closing(sqlite3.connect(database_path)) as connection:
                    repo = InvestigationRepository(connection)
                    if parts == ["api", "customers"]:
                        result = {"grain": "customer_reference_collection", "customers": repo.list_customers()}
                    elif len(parts) == 3 and parts[:2] == ["api", "customers"]:
                        result = repo.get_customer(parts[2])
                    elif len(parts) == 4 and parts[:2] == ["api", "customers"] and parts[3] == "timeline":
                        result = repo.timeline(parts[2])
                    elif len(parts) == 3 and parts[:2] == ["api", "orders"]:
                        result = repo.get_order(parts[2])
                    elif len(parts) == 3 and parts[:2] == ["api", "receipts"]:
                        result = repo.get_receipt(parts[2])
                    elif len(parts) == 3 and parts[:2] == ["api", "payments"]:
                        result = repo.get_payment(parts[2])
                    elif len(parts) == 3 and parts[:2] == ["api", "returns"]:
                        result = repo.get_return(parts[2])
                    else:
                        self._send(404, {"error": "route not found"})
                        return
                self._send(200, result)
            except NotFoundError as exc:
                self._send(404, {"error": str(exc)})
            except Exception:
                self._send(500, {"error": "internal server error"})

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local investigation API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=Path(__file__).with_name("investigation.db"))
    parser.add_argument("--rebuild", action="store_true", help="recreate the database from schema.sql and seed.sql")
    args = parser.parse_args()
    base = Path(__file__).parent
    if args.rebuild or not args.database.exists():
        if args.database.exists():
            args.database.unlink()
        initialize_database(args.database, base / "schema.sql", base / "seed.sql")
    server = ThreadingHTTPServer((args.host, args.port), create_handler(args.database))
    print(f"Investigation API listening at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
