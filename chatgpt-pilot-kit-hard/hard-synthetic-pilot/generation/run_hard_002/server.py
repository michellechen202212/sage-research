"""Minimal local HTTP adapter for the investigation service."""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

from investigation_service import InvestigationService, build_database


SERVICE = InvestigationService(build_database())


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        result = None
        if len(parts) == 3 and parts[:2] == ["v1", "orders"]: result = SERVICE.order(parts[2])
        elif len(parts) == 3 and parts[:2] == ["v1", "payments"]: result = SERVICE.payment(parts[2])
        elif len(parts) == 3 and parts[:2] == ["v1", "receipts"]: result = SERVICE.receipt(parts[2])
        elif len(parts) == 3 and parts[:2] == ["v1", "customers"]: result = SERVICE.customer(parts[2])
        elif parts == ["v1", "compact"]: result = SERVICE.compact(**{k: v[-1] for k, v in parse_qs(parsed.query).items()})
        if result is None:
            result = {"error": "not_found", "entity": "route", "identifier": parsed.path}
        status = 404 if result.get("error") == "not_found" else 400 if "error" in result else 200
        body = json.dumps(result, separators=(",", ":"), sort_keys=True).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)


if __name__ == "__main__":
    print("Listening on http://127.0.0.1:8000")
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()

