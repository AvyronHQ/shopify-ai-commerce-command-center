import os
import tempfile
import unittest
from pathlib import Path

from ai_service import InsightService
from db import CommerceRepository
from shopify_service import ShopifyService


class CommerceCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = CommerceRepository(Path(self.tmp.name) / "test.db")
        self.repo.seed_demo()

    def tearDown(self):
        self.tmp.cleanup()

    def test_dashboard_has_real_computed_metrics(self):
        d = self.repo.dashboard(30)
        self.assertGreater(d["sales"], 0)
        self.assertGreater(d["orders"], 0)
        self.assertGreater(d["aov"], 0)
        self.assertTrue(d["daily_sales"])
        self.assertTrue(d["top_products"])

    def test_inventory_keeps_unknown_data_separate(self):
        rows = self.repo.inventory_health(30)
        unknown = [x for x in rows if x["risk"] == "UNKNOWN"]
        self.assertTrue(unknown)
        self.assertTrue(any(x["sku"] is None or x["inventory"] is None for x in unknown))

    def test_customer_segmentation_is_computed_from_orders(self):
        data = self.repo.customer_segments()
        self.assertIn("customers", data)
        self.assertEqual(sum(data["counts"].values()), len(data["customers"]))
        self.assertTrue(any(c["segment"] in {"VIP", "LOYAL", "REPEAT"} for c in data["customers"]))

    def test_rules_ai_uses_supplied_metrics(self):
        svc = InsightService()
        svc.api_key = ""
        svc.model = ""
        svc.mode = "rules"
        result = svc.insights(self.repo.dashboard(30), self.repo.customer_segments(), self.repo.data_quality())
        self.assertEqual(result["mode"], "rules")
        self.assertTrue(result["items"])
        self.assertIn("sales", result["metrics"])

    def test_shopify_connector_defaults_to_safe_demo_mode(self):
        old_shop = os.environ.pop("SHOPIFY_SHOP_DOMAIN", None)
        old_token = os.environ.pop("SHOPIFY_ACCESS_TOKEN", None)
        try:
            svc = ShopifyService()
            self.assertEqual(svc.mode, "demo")
            result = svc.test_connection()
            self.assertFalse(result["ok"])
        finally:
            if old_shop is not None:
                os.environ["SHOPIFY_SHOP_DOMAIN"] = old_shop
            if old_token is not None:
                os.environ["SHOPIFY_ACCESS_TOKEN"] = old_token


if __name__ == "__main__":
    unittest.main()
