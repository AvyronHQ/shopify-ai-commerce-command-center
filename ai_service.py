from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


class InsightService:
    def __init__(self) -> None:
        self.api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.model = os.getenv("OPENAI_MODEL", "").strip()
        self.mode = "openai" if self.api_key and self.model else "rules"

    def _call_openai(self, payload: dict[str, Any]) -> str:
        prompt = (
            "You are an ecommerce operations analyst. Interpret ONLY the supplied JSON metrics. "
            "Never invent a number, event, cause, benchmark, forecast, or customer fact. "
            "Return 4 concise prioritized insights. Each insight must cite one or more exact supplied metrics. "
            "Use this JSON:\n" + json.dumps(payload, ensure_ascii=False)
        )
        body = json.dumps({"model": self.model, "input": prompt, "max_output_tokens": 650}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=body,
            method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                data = json.loads(res.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            raise RuntimeError(f"AI request failed: {exc}") from exc
        if isinstance(data.get("output_text"), str) and data["output_text"].strip():
            return data["output_text"].strip()
        chunks=[]
        for item in data.get("output", []):
            for part in item.get("content", []):
                if isinstance(part.get("text"), str):
                    chunks.append(part["text"])
        if chunks:
            return "\n".join(chunks).strip()
        raise RuntimeError("AI provider returned no text.")

    def insights(self, dashboard: dict[str, Any], customer_segments: dict[str, Any], data_quality: dict[str, Any]) -> dict[str, Any]:
        safe_payload = {
            "period_days": dashboard.get("period_days"),
            "sales": dashboard.get("sales"),
            "orders": dashboard.get("orders"),
            "aov": dashboard.get("aov"),
            "sales_growth_percent": dashboard.get("sales_growth"),
            "order_growth_percent": dashboard.get("order_growth"),
            "repeat_customer_rate_percent": dashboard.get("repeat_customer_rate"),
            "unfulfilled_orders": dashboard.get("unfulfilled_orders"),
            "inventory_at_risk": dashboard.get("inventory_at_risk"),
            "top_products": dashboard.get("top_products", [])[:5],
            "customer_segment_counts": customer_segments.get("counts", {}),
            "data_quality": {k: data_quality.get(k) for k in ["score","missing_sku","missing_inventory","duplicate_sku","missing_customer_email"]},
        }
        if self.mode == "openai":
            try:
                return {"mode": "openai", "text": self._call_openai(safe_payload), "metrics": safe_payload}
            except Exception as exc:
                fallback = self._rule_insights(safe_payload)
                fallback["warning"] = str(exc)
                return fallback
        return self._rule_insights(safe_payload)

    def _rule_insights(self, m: dict[str, Any]) -> dict[str, Any]:
        items=[]
        growth=float(m.get("sales_growth_percent") or 0)
        if growth >= 8:
            items.append({"priority":"growth","title":"Revenue momentum is positive","detail":f"Sales are up {growth:.1f}% versus the previous comparable period. Protect fulfillment capacity while demand is elevated.","evidence":[f"Sales growth {growth:.1f}%"]})
        elif growth <= -8:
            items.append({"priority":"attention","title":"Sales momentum needs attention","detail":f"Sales are down {abs(growth):.1f}% versus the previous comparable period. Review product mix and channel performance before changing spend.","evidence":[f"Sales growth {growth:.1f}%"]})
        else:
            items.append({"priority":"monitor","title":"Sales are broadly stable","detail":f"Sales changed {growth:.1f}% versus the previous comparable period, so operational improvements may matter more than a major demand response.","evidence":[f"Sales growth {growth:.1f}%"]})

        risk=int(m.get("inventory_at_risk") or 0)
        if risk:
            items.append({"priority":"attention","title":"Inventory risk can block revenue","detail":f"{risk} products are currently flagged as low/critical stock. Review high-velocity items before they become unavailable.","evidence":[f"Inventory at risk {risk}"]})
        else:
            items.append({"priority":"healthy","title":"No immediate low-stock flags","detail":"The current rules do not flag any product as low or critical stock.","evidence":["Inventory at risk 0"]})

        unfulfilled=int(m.get("unfulfilled_orders") or 0)
        if unfulfilled:
            items.append({"priority":"operations","title":"Fulfillment queue deserves a review","detail":f"There are {unfulfilled} not-yet-fulfilled orders inside the selected period. Open Order Ops to identify aging orders and SLA risk.","evidence":[f"Unfulfilled orders {unfulfilled}"]})

        repeat=float(m.get("repeat_customer_rate_percent") or 0)
        items.append({"priority":"retention","title":"Retention has a measurable base","detail":f"{repeat:.1f}% of stored customers have placed at least two orders. Use VIP, loyal, repeat, new, and at-risk segments for targeted actions.","evidence":[f"Repeat customer rate {repeat:.1f}%"]})

        dq=m.get("data_quality") or {}
        if (dq.get("score") or 0) < 100:
            items.append({"priority":"data","title":"Fix data gaps before trusting every recommendation","detail":f"Data quality is {dq.get('score',0)}%. Missing SKU or inventory fields remain intentionally visible instead of being treated as healthy data.","evidence":[f"Data quality {dq.get('score',0)}%"]})
        return {"mode":"rules","items":items[:5],"metrics":m}
