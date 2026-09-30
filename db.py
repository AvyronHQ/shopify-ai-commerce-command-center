from __future__ import annotations

import math
import random
import sqlite3
from contextlib import contextmanager
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def iso_days_ago(days: int, hours: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days, hours=hours)).replace(microsecond=0).isoformat()


class CommerceRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shopify_id TEXT UNIQUE,
                    title TEXT NOT NULL,
                    sku TEXT,
                    vendor TEXT,
                    product_type TEXT,
                    price REAL NOT NULL DEFAULT 0,
                    inventory INTEGER,
                    reorder_point INTEGER NOT NULL DEFAULT 10,
                    status TEXT NOT NULL DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS customers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shopify_id TEXT UNIQUE,
                    name TEXT NOT NULL,
                    email TEXT,
                    country TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shopify_id TEXT UNIQUE,
                    order_name TEXT NOT NULL,
                    customer_id INTEGER,
                    created_at TEXT NOT NULL,
                    total REAL NOT NULL DEFAULT 0,
                    financial_status TEXT NOT NULL DEFAULT 'PAID',
                    fulfillment_status TEXT NOT NULL DEFAULT 'FULFILLED',
                    channel TEXT NOT NULL DEFAULT 'Online Store',
                    currency TEXT NOT NULL DEFAULT 'USD',
                    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS order_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER NOT NULL,
                    product_id INTEGER,
                    sku TEXT,
                    title TEXT NOT NULL,
                    quantity INTEGER NOT NULL DEFAULT 1,
                    unit_price REAL NOT NULL DEFAULT 0,
                    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
                    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    status TEXT NOT NULL,
                    records INTEGER NOT NULL DEFAULT 0,
                    note TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS webhook_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    shop_domain TEXT DEFAULT '',
                    payload TEXT DEFAULT '',
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
                CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
                CREATE INDEX IF NOT EXISTS idx_items_product ON order_items(product_id);
                CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
                """
            )

    def is_empty(self) -> bool:
        with self._connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 0

    def reset(self) -> None:
        with self._connection() as conn:
            for table in ["order_items", "orders", "customers", "products", "sync_runs", "webhook_events"]:
                conn.execute(f"DELETE FROM {table}")
        self.seed_demo()

    def seed_demo(self) -> None:
        if not self.is_empty():
            return
        rng = random.Random(260930)
        now = datetime.now(timezone.utc)

        product_seed = [
            ("Midnight Truffle Collection", "CHO-TRF-12", "Aurum Cacao", "Gift Box", 48.0, 36, 14),
            ("Sea Salt Caramel Bar", "CHO-SC-70", "Aurum Cacao", "Chocolate Bar", 12.0, 18, 20),
            ("Single Origin 72%", "CHO-72-90", "Aurum Cacao", "Chocolate Bar", 15.0, 62, 18),
            ("Pistachio Praline Box", "CHO-PST-09", "Aurum Cacao", "Gift Box", 36.0, 9, 16),
            ("Espresso Ganache Bites", "CHO-ESP-16", "Aurum Cacao", "Bites", 22.0, 44, 18),
            ("Hazelnut Gianduja Bar", "CHO-HZ-70", "Aurum Cacao", "Chocolate Bar", 14.0, 27, 18),
            ("Signature Discovery Box", "CHO-DSC-18", "Aurum Cacao", "Gift Box", 58.0, 21, 12),
            ("Dark Chocolate Almonds", "CHO-ALM-150", "Aurum Cacao", "Snacks", 18.0, 74, 24),
            ("Orange Peel Batons", "CHO-ORG-120", "Aurum Cacao", "Snacks", 24.0, 11, 14),
            ("Corporate Tasting Set", "CHO-B2B-24", "Aurum Cacao", "Corporate", 84.0, 15, 8),
            ("Mini Thank You Box", "CHO-TY-06", "Aurum Cacao", "Gift Box", 26.0, 55, 18),
            ("Seasonal Limited Reserve", None, "Aurum Cacao", "Limited", 42.0, None, 10),
        ]

        product_ids: list[int] = []
        with self._connection() as conn:
            for i, (title, sku, vendor, ptype, price, inv, reorder) in enumerate(product_seed, 1):
                cur = conn.execute(
                    """INSERT INTO products
                    (shopify_id,title,sku,vendor,product_type,price,inventory,reorder_point,status,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (f"gid://shopify/Product/{1000+i}", title, sku, vendor, ptype, price, inv, reorder, "ACTIVE", iso_days_ago(240-i), utc_now()),
                )
                product_ids.append(cur.lastrowid)

        first_names = ["Maya","Noah","Sofia","Ethan","Ava","Liam","Isla","Lucas","Chloe","Oliver","Amelia","James","Mia","Leo","Nora","Henry","Zoe","Theo","Ivy","Jack","Ella","Finn","Lily","Oscar","Grace","Milo","Ruby","Arlo","Layla","Kai"]
        last_names = ["Brooks","Cole","Patel","Bennett","Morgan","Foster","Turner","Kim","Reed","Grant","Davis","Wilson","Chen","Brown","Martinez","Clark","Taylor","Lewis","Walker","Hall"]
        countries = ["US","US","US","US","CA","GB","US","AU"]

        customer_ids: list[int] = []
        with self._connection() as conn:
            for i in range(150):
                name = f"{rng.choice(first_names)} {rng.choice(last_names)}"
                email = f"customer{i+1}@demo.example"
                created_days = rng.randint(20, 400)
                cur = conn.execute(
                    """INSERT INTO customers(shopify_id,name,email,country,created_at,updated_at)
                    VALUES(?,?,?,?,?,?)""",
                    (f"gid://shopify/Customer/{5000+i}", name, email, rng.choice(countries), iso_days_ago(created_days), utc_now()),
                )
                customer_ids.append(cur.lastrowid)

        channels = ["Online Store"] * 65 + ["Shop App"] * 12 + ["Instagram"] * 10 + ["Draft Order"] * 5 + ["POS"] * 8
        financial = ["PAID"] * 92 + ["PENDING"] * 5 + ["REFUNDED"] * 3
        order_counter = 2100
        with self._connection() as conn:
            for day in range(179, -1, -1):
                season = 1.0 + (0.30 if day < 18 else 0.0) + (0.15 if 55 < day < 75 else 0.0)
                weekday = (now - timedelta(days=day)).weekday()
                base = 3.1 if weekday < 5 else 4.0
                count = max(1, int(rng.gauss(base * season, 1.4)))
                for _ in range(count):
                    if rng.random() < 0.65:
                        customer_id = rng.choice(customer_ids[:65])
                    else:
                        customer_id = rng.choice(customer_ids)
                    created = now - timedelta(days=day, hours=rng.randint(0, 22), minutes=rng.randint(0, 59))
                    item_count = rng.choices([1,2,3,4], weights=[50,30,15,5])[0]
                    chosen = [rng.randrange(len(product_ids)-1) for _ in range(item_count)]
                    rows = []
                    total = 0.0
                    for idx in chosen:
                        qty = rng.choices([1,2,3], weights=[78,18,4])[0]
                        price = product_seed[idx][4]
                        rows.append((product_ids[idx], product_seed[idx][1], product_seed[idx][0], qty, price))
                        total += qty * price
                    if total > 120 and rng.random() < 0.16:
                        total *= 0.90
                    status = rng.choice(financial)
                    age_hours = (now-created).total_seconds()/3600
                    if age_hours < 18:
                        fulfillment = rng.choice(["UNFULFILLED","UNFULFILLED","FULFILLED"])
                    elif age_hours < 48:
                        fulfillment = rng.choice(["FULFILLED","FULFILLED","PARTIALLY_FULFILLED","UNFULFILLED"])
                    else:
                        fulfillment = rng.choice(["FULFILLED"]*93 + ["UNFULFILLED"]*7)
                    cur = conn.execute(
                        """INSERT INTO orders(shopify_id,order_name,customer_id,created_at,total,financial_status,fulfillment_status,channel,currency)
                        VALUES(?,?,?,?,?,?,?,?,?)""",
                        (f"gid://shopify/Order/{900000+order_counter}", f"#{order_counter}", customer_id, created.replace(microsecond=0).isoformat(), round(total,2), status, fulfillment, rng.choice(channels), "USD"),
                    )
                    oid = cur.lastrowid
                    for pid, sku, title, qty, price in rows:
                        conn.execute(
                            "INSERT INTO order_items(order_id,product_id,sku,title,quantity,unit_price) VALUES(?,?,?,?,?,?)",
                            (oid,pid,sku,title,qty,price),
                        )
                    order_counter += 1
            conn.execute(
                "INSERT INTO sync_runs(mode,status,records,note,created_at) VALUES(?,?,?,?,?)",
                ("DEMO","SUCCESS",order_counter-2100,"Demo commerce dataset generated.",utc_now()),
            )

    def _period_start(self, days: int) -> str:
        return (datetime.now(timezone.utc) - timedelta(days=max(1, days))).replace(microsecond=0).isoformat()

    def dashboard(self, days: int = 30) -> dict[str, Any]:
        start = self._period_start(days)
        prev_start = self._period_start(days * 2)
        with self._connection() as conn:
            current = conn.execute(
                "SELECT COUNT(*) c, COALESCE(SUM(total),0) sales, COALESCE(AVG(total),0) aov FROM orders WHERE created_at >= ? AND financial_status != 'REFUNDED'",
                (start,),
            ).fetchone()
            prev = conn.execute(
                "SELECT COUNT(*) c, COALESCE(SUM(total),0) sales FROM orders WHERE created_at >= ? AND created_at < ? AND financial_status != 'REFUNDED'",
                (prev_start, start),
            ).fetchone()
            unique = conn.execute("SELECT COUNT(DISTINCT customer_id) FROM orders WHERE created_at >= ?", (start,)).fetchone()[0]
            repeat = conn.execute(
                """SELECT COUNT(*) FROM (
                    SELECT customer_id FROM orders WHERE customer_id IS NOT NULL GROUP BY customer_id HAVING COUNT(*) >= 2
                )"""
            ).fetchone()[0]
            all_customers = conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            unfulfilled = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE fulfillment_status != 'FULFILLED' AND created_at >= ?", (start,)
            ).fetchone()[0]
            low_stock = self.inventory_health(days=30, conn=conn)
            daily = [dict(r) for r in conn.execute(
                """SELECT substr(created_at,1,10) day, ROUND(SUM(CASE WHEN financial_status!='REFUNDED' THEN total ELSE 0 END),2) sales, COUNT(*) orders
                FROM orders WHERE created_at >= ? GROUP BY substr(created_at,1,10) ORDER BY day""", (start,)
            ).fetchall()]
            channels = [dict(r) for r in conn.execute(
                "SELECT channel, ROUND(SUM(total),2) sales, COUNT(*) orders FROM orders WHERE created_at >= ? AND financial_status!='REFUNDED' GROUP BY channel ORDER BY sales DESC", (start,)
            ).fetchall()]
            latest = conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 1").fetchone()

        sales_growth = ((current["sales"] - prev["sales"]) / prev["sales"] * 100) if prev["sales"] else 0
        order_growth = ((current["c"] - prev["c"]) / prev["c"] * 100) if prev["c"] else 0
        return {
            "period_days": days,
            "sales": round(current["sales"],2),
            "orders": current["c"],
            "aov": round(current["aov"],2),
            "unique_customers": unique,
            "sales_growth": round(sales_growth,1),
            "order_growth": round(order_growth,1),
            "repeat_customer_rate": round((repeat / all_customers * 100) if all_customers else 0,1),
            "unfulfilled_orders": unfulfilled,
            "inventory_at_risk": sum(1 for p in low_stock if p["risk"] in {"CRITICAL","LOW"}),
            "daily_sales": daily,
            "channels": channels,
            "last_sync": dict(latest) if latest else None,
            "top_products": self.top_products(days, 6),
            "alerts": self.alerts(),
        }

    def top_products(self, days: int = 30, limit: int = 10) -> list[dict[str, Any]]:
        start = self._period_start(days)
        with self._connection() as conn:
            rows = conn.execute(
                """SELECT p.id,p.title,p.sku,p.inventory, SUM(oi.quantity) units,
                ROUND(SUM(oi.quantity*oi.unit_price),2) revenue
                FROM order_items oi JOIN orders o ON o.id=oi.order_id
                LEFT JOIN products p ON p.id=oi.product_id
                WHERE o.created_at >= ? AND o.financial_status!='REFUNDED'
                GROUP BY p.id,p.title,p.sku,p.inventory ORDER BY revenue DESC LIMIT ?""",
                (start, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_orders(self, limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
        sql = """SELECT o.*, c.name customer_name,c.email customer_email,
                 (SELECT SUM(quantity) FROM order_items WHERE order_id=o.id) item_count
                 FROM orders o LEFT JOIN customers c ON c.id=o.customer_id WHERE 1=1"""
        params: list[Any] = []
        if status:
            sql += " AND o.fulfillment_status=?"
            params.append(status)
        sql += " ORDER BY o.created_at DESC LIMIT ?"
        params.append(limit)
        with self._connection() as conn:
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def order_detail(self, order_id: int) -> dict[str, Any] | None:
        with self._connection() as conn:
            row = conn.execute(
                """SELECT o.*, c.name customer_name,c.email customer_email,c.country customer_country
                FROM orders o LEFT JOIN customers c ON c.id=o.customer_id WHERE o.id=?""", (order_id,)
            ).fetchone()
            if not row:
                return None
            data = dict(row)
            data["items"] = [dict(r) for r in conn.execute("SELECT * FROM order_items WHERE order_id=?", (order_id,)).fetchall()]
            return data

    def inventory_health(self, days: int = 30, conn: sqlite3.Connection | None = None) -> list[dict[str, Any]]:
        own = conn is None
        if own:
            conn = self._connect()
        assert conn is not None
        start = self._period_start(days)
        rows = conn.execute(
            """SELECT p.*, COALESCE(SUM(CASE WHEN o.created_at>=? THEN oi.quantity ELSE 0 END),0) units_30
            FROM products p LEFT JOIN order_items oi ON oi.product_id=p.id
            LEFT JOIN orders o ON o.id=oi.order_id
            GROUP BY p.id ORDER BY p.title""", (start,)
        ).fetchall()
        out=[]
        for r in rows:
            d=dict(r)
            inventory=d.get("inventory")
            units=float(d.get("units_30") or 0)
            daily=units/max(days,1)
            days_cover = None if inventory is None else (999 if daily == 0 else inventory/daily)
            if inventory is None or not d.get("sku"):
                risk="UNKNOWN"
            elif inventory <= 0:
                risk="CRITICAL"
            elif inventory <= d["reorder_point"] or (days_cover is not None and days_cover < 12):
                risk="LOW"
            elif days_cover is not None and days_cover < 25:
                risk="WATCH"
            else:
                risk="HEALTHY"
            d["daily_velocity"]=round(daily,2)
            d["days_cover"]=None if days_cover is None else (round(days_cover,1) if days_cover < 900 else 999)
            d["risk"]=risk
            out.append(d)
        if own:
            conn.close()
        order={"CRITICAL":0,"LOW":1,"WATCH":2,"UNKNOWN":3,"HEALTHY":4}
        out.sort(key=lambda x:(order[x["risk"]], x.get("days_cover") if x.get("days_cover") is not None else 9999))
        return out

    def customer_segments(self) -> dict[str, Any]:
        now=datetime.now(timezone.utc)
        with self._connection() as conn:
            rows=conn.execute(
                """SELECT c.id,c.name,c.email,c.country,COUNT(o.id) orders,COALESCE(SUM(CASE WHEN o.financial_status!='REFUNDED' THEN o.total ELSE 0 END),0) spend,MAX(o.created_at) last_order
                FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.id ORDER BY spend DESC"""
            ).fetchall()
        customers=[]
        counts=defaultdict(int)
        for r in rows:
            d=dict(r)
            last=datetime.fromisoformat(d["last_order"]) if d["last_order"] else None
            recency=(now-last).days if last else 999
            orders=int(d["orders"] or 0)
            spend=float(d["spend"] or 0)
            if orders >= 8 or spend >= 1200:
                segment="VIP"
            elif orders >= 4:
                segment="LOYAL"
            elif orders >= 2 and recency > 60:
                segment="AT_RISK"
            elif orders == 1 and recency <= 45:
                segment="NEW"
            elif orders >= 2:
                segment="REPEAT"
            else:
                segment="DORMANT"
            d["segment"]=segment
            d["recency_days"]=recency
            d["spend"]=round(spend,2)
            counts[segment]+=1
            customers.append(d)
        return {"counts":dict(counts),"customers":customers}

    def product_catalog(self) -> list[dict[str, Any]]:
        return self.inventory_health(30)

    def data_quality(self) -> dict[str, Any]:
        with self._connection() as conn:
            missing_sku=conn.execute("SELECT COUNT(*) FROM products WHERE sku IS NULL OR trim(sku)='' ").fetchone()[0]
            missing_inventory=conn.execute("SELECT COUNT(*) FROM products WHERE inventory IS NULL").fetchone()[0]
            duplicate_sku=conn.execute("SELECT COUNT(*) FROM (SELECT sku FROM products WHERE sku IS NOT NULL GROUP BY sku HAVING COUNT(*)>1)").fetchone()[0]
            missing_email=conn.execute("SELECT COUNT(*) FROM customers WHERE email IS NULL OR trim(email)='' ").fetchone()[0]
            total_products=conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
            total_customers=conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
            syncs=[dict(r) for r in conn.execute("SELECT * FROM sync_runs ORDER BY id DESC LIMIT 8").fetchall()]
        issues=missing_sku+missing_inventory+duplicate_sku
        score=max(0,100-round((issues/max(total_products,1))*100))
        return {"score":score,"missing_sku":missing_sku,"missing_inventory":missing_inventory,"duplicate_sku":duplicate_sku,"missing_customer_email":missing_email,"products":total_products,"customers":total_customers,"sync_runs":syncs}

    def alerts(self) -> list[dict[str, Any]]:
        alerts=[]
        for p in self.inventory_health(30):
            if p["risk"] in {"CRITICAL","LOW","UNKNOWN"}:
                severity="critical" if p["risk"]=="CRITICAL" else "warning"
                if p["risk"]=="UNKNOWN":
                    title=f"Data gap: {p['title']}"
                    detail="SKU or inventory is missing, so stock health cannot be trusted."
                else:
                    title=f"Stock risk: {p['title']}"
                    detail=f"{p['inventory']} units on hand · {p['days_cover']} days of cover."
                alerts.append({"severity":severity,"type":"inventory","title":title,"detail":detail})
        cutoff=(datetime.now(timezone.utc)-timedelta(hours=48)).replace(microsecond=0).isoformat()
        with self._connection() as conn:
            delayed=conn.execute(
                "SELECT COUNT(*) FROM orders WHERE fulfillment_status!='FULFILLED' AND created_at < ? AND financial_status='PAID'",(cutoff,)
            ).fetchone()[0]
        if delayed:
            alerts.insert(0,{"severity":"warning","type":"fulfillment","title":f"{delayed} fulfillment SLA risks","detail":"Paid orders older than 48 hours are still not fulfilled."})
        dq=self.data_quality()
        if dq["score"]<100:
            alerts.append({"severity":"info","type":"data","title":f"Data quality score {dq['score']}%","detail":"Resolve missing SKU/inventory fields before relying on all recommendations."})
        return alerts[:12]

    def add_sync_run(self, mode: str, status: str, records: int, note: str) -> dict[str, Any]:
        with self._connection() as conn:
            cur=conn.execute("INSERT INTO sync_runs(mode,status,records,note,created_at) VALUES(?,?,?,?,?)",(mode,status,records,note,utc_now()))
            return dict(conn.execute("SELECT * FROM sync_runs WHERE id=?",(cur.lastrowid,)).fetchone())

    def record_webhook(self, topic: str, shop_domain: str, payload: str) -> None:
        with self._connection() as conn:
            conn.execute("INSERT INTO webhook_events(topic,shop_domain,payload,created_at) VALUES(?,?,?,?)",(topic,shop_domain,payload[:20000],utc_now()))

    def replace_from_shopify(self, data: dict[str, Any]) -> dict[str, int]:
        """Upsert a deliberately small live snapshot from Shopify GraphQL results."""
        counts={"products":0,"customers":0,"orders":0}
        products=data.get("products",[])
        customers=data.get("customers",[])
        orders=data.get("orders",[])
        with self._connection() as conn:
            product_map={}
            for p in products:
                sku=p.get("sku")
                conn.execute(
                    """INSERT INTO products(shopify_id,title,sku,vendor,product_type,price,inventory,reorder_point,status,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(shopify_id) DO UPDATE SET title=excluded.title,sku=excluded.sku,vendor=excluded.vendor,product_type=excluded.product_type,price=excluded.price,inventory=excluded.inventory,status=excluded.status,updated_at=excluded.updated_at""",
                    (p["shopify_id"],p.get("title","Untitled"),sku,p.get("vendor",""),p.get("product_type",""),p.get("price",0),p.get("inventory"),10,p.get("status","ACTIVE"),p.get("created_at",utc_now()),utc_now())
                )
                pid=conn.execute("SELECT id FROM products WHERE shopify_id=?",(p["shopify_id"],)).fetchone()[0]
                product_map[p["shopify_id"]]=pid
                counts["products"]+=1
            customer_map={}
            for c in customers:
                conn.execute(
                    """INSERT INTO customers(shopify_id,name,email,country,created_at,updated_at) VALUES(?,?,?,?,?,?)
                    ON CONFLICT(shopify_id) DO UPDATE SET name=excluded.name,email=excluded.email,country=excluded.country,updated_at=excluded.updated_at""",
                    (c["shopify_id"],c.get("name","Customer"),c.get("email"),c.get("country",""),c.get("created_at",utc_now()),utc_now())
                )
                cid=conn.execute("SELECT id FROM customers WHERE shopify_id=?",(c["shopify_id"],)).fetchone()[0]
                customer_map[c["shopify_id"]]=cid
                counts["customers"]+=1
            for o in orders:
                cid=customer_map.get(o.get("customer_shopify_id"))
                conn.execute(
                    """INSERT INTO orders(shopify_id,order_name,customer_id,created_at,total,financial_status,fulfillment_status,channel,currency)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(shopify_id) DO UPDATE SET order_name=excluded.order_name,customer_id=excluded.customer_id,created_at=excluded.created_at,total=excluded.total,financial_status=excluded.financial_status,fulfillment_status=excluded.fulfillment_status,channel=excluded.channel,currency=excluded.currency""",
                    (o["shopify_id"],o.get("order_name","Order"),cid,o.get("created_at",utc_now()),o.get("total",0),o.get("financial_status","PAID"),o.get("fulfillment_status","UNFULFILLED"),o.get("channel","Shopify"),o.get("currency","USD"))
                )
                oid=conn.execute("SELECT id FROM orders WHERE shopify_id=?",(o["shopify_id"],)).fetchone()[0]
                conn.execute("DELETE FROM order_items WHERE order_id=?",(oid,))
                for item in o.get("items",[]):
                    pid=product_map.get(item.get("product_shopify_id"))
                    conn.execute("INSERT INTO order_items(order_id,product_id,sku,title,quantity,unit_price) VALUES(?,?,?,?,?,?)",(oid,pid,item.get("sku"),item.get("title","Item"),item.get("quantity",1),item.get("unit_price",0)))
                counts["orders"]+=1
        return counts
