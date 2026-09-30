from __future__ import annotations

import base64
import hashlib
import hmac
import json
import mimetypes
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ai_service import InsightService
from db import CommerceRepository, utc_now
from shopify_service import ShopifyService

BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = BASE_DIR / "frontend"
DATA_DIR = BASE_DIR / "data"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(BASE_DIR / ".env")
db_path = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "commerce_command.db")))
if not db_path.is_absolute():
    db_path = (BASE_DIR / db_path).resolve()
repo = CommerceRepository(db_path)
repo.seed_demo()
shopify = ShopifyService()
ai = InsightService()


class Handler(BaseHTTPRequestHandler):
    server_version = "CommerceCommand/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def _json(self, payload, status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        self._json({"error": message}, status)

    def _read_body(self, max_bytes: int = 2_000_000) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 0 or length > max_bytes:
            raise ValueError("Request body is too large.")
        return self.rfile.read(length) if length else b""

    def _read_json(self) -> dict:
        raw = self._read_body()
        if not raw:
            return {}
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body.") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")
        return data

    def _serve_file(self, relative: str) -> None:
        target = (FRONTEND_DIR / relative).resolve()
        try:
            target.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            return self._error("Not found", HTTPStatus.NOT_FOUND)
        if not target.is_file():
            return self._error("Not found", HTTPStatus.NOT_FOUND)
        content = target.read_bytes()
        mime, _ = mimetypes.guess_type(target.name)
        ctype = mime or "application/octet-stream"
        if ctype.startswith("text/") or ctype in {"application/javascript", "application/json"}:
            ctype += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)

    @staticmethod
    def _days(query: dict) -> int:
        try:
            value = int(query.get("days", [30])[0])
        except (ValueError, TypeError):
            value = 30
        return min(max(value, 7), 180)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            return self._serve_file("index.html")
        if path in {"/styles.css", "/app.js"}:
            return self._serve_file(path.lstrip("/"))

        if path == "/api/health":
            return self._json({
                "status": "ok",
                "time": utc_now(),
                "shopify_mode": shopify.mode,
                "ai_mode": ai.mode,
                "shop": shopify.shop or "demo-store.myshopify.com",
                "api_version": shopify.api_version,
            })
        if path == "/api/dashboard":
            return self._json(repo.dashboard(self._days(query)))
        if path == "/api/orders":
            try:
                limit = min(max(int(query.get("limit", [60])[0]), 1), 200)
            except ValueError:
                limit = 60
            return self._json({"orders": repo.list_orders(limit=limit, status=query.get("status", [None])[0])})
        match = re.match(r"^/api/orders/(\d+)$", path)
        if match:
            order = repo.order_detail(int(match.group(1)))
            return self._json(order) if order else self._error("Order not found", HTTPStatus.NOT_FOUND)
        if path == "/api/inventory":
            return self._json({"products": repo.inventory_health(self._days(query))})
        if path == "/api/products":
            return self._json({"products": repo.product_catalog()})
        if path == "/api/customers":
            return self._json(repo.customer_segments())
        if path == "/api/data-quality":
            return self._json(repo.data_quality())
        if path == "/api/alerts":
            return self._json({"alerts": repo.alerts()})
        if path == "/api/insights":
            days = self._days(query)
            return self._json(ai.insights(repo.dashboard(days), repo.customer_segments(), repo.data_quality()))
        if path == "/api/shopify/connection":
            if shopify.mode == "demo":
                return self._json(shopify.test_connection())
            try:
                return self._json(shopify.test_connection())
            except Exception as exc:
                return self._error(str(exc), HTTPStatus.BAD_GATEWAY)

        self._error("Not found", HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/demo/reset":
            repo.reset()
            return self._json({"message": "Demo dataset restored.", "dashboard": repo.dashboard(30)})

        if path == "/api/shopify/test":
            try:
                return self._json(shopify.test_connection())
            except Exception as exc:
                return self._error(str(exc), HTTPStatus.BAD_GATEWAY)

        if path == "/api/shopify/sync":
            if shopify.mode != "live":
                return self._error("Live Shopify credentials are not configured. Demo data remains active.", HTTPStatus.CONFLICT)
            try:
                snapshot = shopify.fetch_snapshot()
                counts = repo.replace_from_shopify(snapshot)
                total = sum(counts.values())
                run = repo.add_sync_run("SHOPIFY", "SUCCESS", total, f"Live snapshot synced: {counts}")
                return self._json({"message": "Shopify snapshot synchronized.", "counts": counts, "sync": run})
            except Exception as exc:
                repo.add_sync_run("SHOPIFY", "FAILED", 0, str(exc)[:500])
                return self._error(str(exc), HTTPStatus.BAD_GATEWAY)

        if path == "/webhooks/shopify":
            try:
                raw = self._read_body(max_bytes=5_000_000)
            except ValueError as exc:
                return self._error(str(exc), HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            secret = os.getenv("SHOPIFY_API_SECRET", "").strip()
            provided = self.headers.get("X-Shopify-Hmac-Sha256", "")
            if secret:
                digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
                expected = base64.b64encode(digest).decode("ascii")
                if not provided or not hmac.compare_digest(expected, provided):
                    return self._error("Invalid Shopify webhook signature.", HTTPStatus.UNAUTHORIZED)
            topic = self.headers.get("X-Shopify-Topic", "unknown")
            shop_domain = self.headers.get("X-Shopify-Shop-Domain", "")
            repo.record_webhook(topic, shop_domain, raw.decode("utf-8", "replace"))
            return self._json({"received": True, "topic": topic})

        self._error("Not found", HTTPStatus.NOT_FOUND)


def main() -> None:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8020"))
    server = ThreadingHTTPServer((host, port), Handler)
    print("\nShopify AI Commerce Command Center")
    print(f"Dashboard: http://{host}:{port}")
    print(f"Shopify mode: {shopify.mode} · AI mode: {ai.mode}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
