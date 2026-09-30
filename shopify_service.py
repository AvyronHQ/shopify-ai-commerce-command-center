from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class ShopifyService:
    def __init__(self) -> None:
        raw_shop = os.getenv("SHOPIFY_SHOP_DOMAIN", "").strip()
        raw_shop = raw_shop.replace("https://", "").replace("http://", "").strip("/")
        if raw_shop and not raw_shop.endswith(".myshopify.com"):
            raw_shop = f"{raw_shop}.myshopify.com"
        self.shop = raw_shop
        self.token = os.getenv("SHOPIFY_ACCESS_TOKEN", "").strip()
        self.api_version = os.getenv("SHOPIFY_API_VERSION", "2026-07").strip() or "2026-07"
        self.mode = "live" if self.shop and self.token else "demo"

    @property
    def endpoint(self) -> str:
        return f"https://{self.shop}/admin/api/{self.api_version}/graphql.json"

    def _query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.mode != "live":
            raise RuntimeError("Shopify credentials are not configured.")
        payload = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.token,
                "User-Agent": "Shopify-Commerce-Command-Center/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1000]
            raise RuntimeError(f"Shopify API returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RuntimeError(f"Could not reach Shopify: {exc}") from exc
        if body.get("errors"):
            raise RuntimeError("Shopify GraphQL error: " + json.dumps(body["errors"])[:1500])
        return body.get("data", {})

    def test_connection(self) -> dict[str, Any]:
        if self.mode != "live":
            return {"ok": False, "mode": "demo", "message": "Add SHOPIFY_SHOP_DOMAIN and SHOPIFY_ACCESS_TOKEN to .env for live sync."}
        data = self._query("query { shop { name myshopifyDomain currencyCode } }")
        shop = data.get("shop") or {}
        return {"ok": True, "mode": "live", "shop": shop}

    def fetch_snapshot(self) -> dict[str, Any]:
        """Fetch a compact portfolio-friendly snapshot.

        This is intentionally synchronous and bounded. Production stores with large history
        should use Shopify GraphQL bulk operations plus webhooks for incremental sync.
        """
        product_query = """
        query ProductSnapshot($first:Int!) {
          products(first:$first, sortKey:UPDATED_AT, reverse:true) {
            nodes {
              id title vendor productType status createdAt totalInventory
              variants(first:25) { nodes { id sku price inventoryQuantity } }
            }
          }
        }
        """
        customer_query = """
        query CustomerSnapshot($first:Int!) {
          customers(first:$first, sortKey:UPDATED_AT, reverse:true) {
            nodes { id displayName email createdAt defaultAddress { countryCodeV2 } }
          }
        }
        """
        order_query = """
        query OrderSnapshot($first:Int!) {
          orders(first:$first, sortKey:CREATED_AT, reverse:true) {
            nodes {
              id name createdAt displayFinancialStatus displayFulfillmentStatus
              totalPriceSet { shopMoney { amount currencyCode } }
              customer { id }
              channelInformation { channelDefinition { channelName } }
              lineItems(first:50) {
                nodes {
                  title quantity sku
                  originalUnitPriceSet { shopMoney { amount currencyCode } }
                  product { id }
                }
              }
            }
          }
        }
        """
        product_data = self._query(product_query, {"first": 100})
        customer_data = self._query(customer_query, {"first": 100})
        order_data = self._query(order_query, {"first": 100})

        products = []
        for p in (product_data.get("products") or {}).get("nodes", []):
            variants = (p.get("variants") or {}).get("nodes", [])
            first_variant = variants[0] if variants else {}
            inventory = p.get("totalInventory")
            products.append({
                "shopify_id": p["id"],
                "title": p.get("title") or "Untitled",
                "sku": first_variant.get("sku"),
                "vendor": p.get("vendor") or "",
                "product_type": p.get("productType") or "",
                "price": float(first_variant.get("price") or 0),
                "inventory": inventory,
                "status": p.get("status") or "ACTIVE",
                "created_at": p.get("createdAt"),
            })

        customers = []
        for c in (customer_data.get("customers") or {}).get("nodes", []):
            address = c.get("defaultAddress") or {}
            customers.append({
                "shopify_id": c["id"],
                "name": c.get("displayName") or "Customer",
                "email": c.get("email"),
                "country": address.get("countryCodeV2") or "",
                "created_at": c.get("createdAt"),
            })

        orders = []
        for o in (order_data.get("orders") or {}).get("nodes", []):
            money = ((o.get("totalPriceSet") or {}).get("shopMoney") or {})
            channel = ((((o.get("channelInformation") or {}).get("channelDefinition") or {}).get("channelName")) or "Shopify")
            items = []
            for item in (o.get("lineItems") or {}).get("nodes", []):
                unit_money = ((item.get("originalUnitPriceSet") or {}).get("shopMoney") or {})
                items.append({
                    "title": item.get("title") or "Item",
                    "quantity": int(item.get("quantity") or 1),
                    "sku": item.get("sku"),
                    "unit_price": float(unit_money.get("amount") or 0),
                    "product_shopify_id": (item.get("product") or {}).get("id"),
                })
            orders.append({
                "shopify_id": o["id"],
                "order_name": o.get("name") or "Order",
                "created_at": o.get("createdAt"),
                "total": float(money.get("amount") or 0),
                "currency": money.get("currencyCode") or "USD",
                "financial_status": o.get("displayFinancialStatus") or "PENDING",
                "fulfillment_status": o.get("displayFulfillmentStatus") or "UNFULFILLED",
                "channel": channel,
                "customer_shopify_id": (o.get("customer") or {}).get("id"),
                "items": items,
            })
        return {"products": products, "customers": customers, "orders": orders}
