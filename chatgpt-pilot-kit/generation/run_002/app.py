"""Minimal deterministic HTTP API (Python standard library only)."""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from repository import InvestigationRepository, NotFound, connect, initialize


def build_repository(database: str | Path | None = None) -> InvestigationRepository:
    db = connect(database or ":memory:")
    if database is None or not Path(database).exists() or not db.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
        initialize(db)
    return InvestigationRepository(db)


def dispatch(repo: InvestigationRepository, path: str):
    parts = [unquote(x) for x in path.strip("/").split("/") if x]
    if parts == ["api", "customers"]:
        return {"grain": "customer_collection", "customers": repo.customers()}
    if len(parts) >= 3 and parts[:2] == ["api", "customers"]:
        cid = parts[2]
        if len(parts) == 3: return repo.customer(cid)
        actions = {"activity": repo.activity, "orders": repo.orders, "receipts": repo.receipts,
                   "returns": repo.returns, "timeline": repo.timeline}
        if len(parts) == 4 and parts[3] in actions:
            value = actions[parts[3]](cid)
            return value if isinstance(value, dict) else {"grain": parts[3].rstrip("s") + "_collection", parts[3]: value}
    if len(parts) == 3 and parts[:2] == ["api", "orders"]: return repo.order(parts[2])
    if len(parts) == 3 and parts[:2] == ["api", "receipts"]: return repo.receipt(parts[2])
    if len(parts) == 3 and parts[:2] == ["api", "payments"]: return repo.payment(parts[2])
    raise NotFound("route")


class Handler(BaseHTTPRequestHandler):
    repo: InvestigationRepository

    def do_GET(self):
        try:
            body, status = dispatch(self.repo, urlparse(self.path).path), 200
        except NotFound as exc:
            body, status = {"grain": "api_error", "error": "not_found", "entity": str(exc)}, 404
        except Exception:
            body, status = {"grain": "api_error", "error": "internal_error"}, 500
        encoded = json.dumps(body, indent=2).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded))); self.end_headers(); self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic commerce investigation API")
    parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", help="Optional persistent SQLite database")
    args = parser.parse_args()
    Handler.repo = build_repository(args.database)
    print(f"Investigation API listening on http://{args.host}:{args.port}")
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
