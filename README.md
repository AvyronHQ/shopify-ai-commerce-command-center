# Shopify AI Commerce Command Center

A full-stack portfolio project for the type of internal ecommerce tooling Shopify brands are actively hiring freelancers to build: fast owner-friendly dashboards, Shopify API integration, sales and inventory visibility, customer segmentation, data-quality controls, and AI-assisted business interpretation.

## What it demonstrates

- Executive Shopify business pulse with net sales, orders, AOV and repeat-customer rate
- Daily sales trend and channel mix
- Product revenue ranking
- Order operations queue with payment/fulfillment status and aging
- Order drill-down with customer and line-item context
- Inventory health based on 30-day sales velocity, days of cover and reorder points
- Explicit `UNKNOWN` inventory/data states — missing data is never shown as healthy
- Customer segmentation: VIP, Loyal, Repeat, New, At Risk, Dormant
- Action queue for stock, fulfillment and data-quality issues
- Evidence-grounded AI business brief
- Data-quality score and sync history
- Optional live Shopify GraphQL Admin API snapshot connector
- Shopify webhook receiver with optional HMAC verification
- Demo mode requiring no API key, paid service or external dependency
- Unit tests and Windows / WSL / Linux launch scripts

## Design principle

The AI does **not** calculate business numbers. Python/SQLite computes the metrics first. The AI receives only a controlled evidence payload and is instructed to interpret those values without inventing numbers, causes, forecasts or benchmarks.

## Stack

**Frontend:** HTML5, CSS3, Vanilla JavaScript, SVG charts  
**Backend:** Python standard-library HTTP server  
**Database:** SQLite  
**Shopify:** GraphQL Admin API-ready connector (default API version `2026-07`)  
**AI:** local deterministic insight engine + optional OpenAI Responses API  
**Webhooks:** Shopify HMAC verification scaffold when `SHOPIFY_API_SECRET` is configured

No third-party Python package is required for the demo.

## Quick start

### Windows

```powershell
cd shopify-ai-commerce-command-center
python app.py
```

Or double-click `run.bat`.

### WSL / Linux / macOS

```bash
cd shopify-ai-commerce-command-center
./run.sh
```

Open:

```text
http://127.0.0.1:8020
```

The demo database is created automatically at `data/commerce_command.db`.

## Demo sections

- **Pulse** — KPIs, daily sales, action queue, top products and channel mix
- **Sales** — larger trend view, product ranking, channel economics
- **Order Ops** — searchable fulfillment queue and order detail
- **Inventory** — units on hand, velocity, days of cover and risk state
- **Customers** — behavior-derived segments and lifetime spend
- **AI Brief** — evidence-grounded operational recommendations
- **Data** — connection state, quality issues, sync history

## Optional live Shopify setup

Copy `.env.example` to `.env` and fill:

```env
SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=your_admin_api_access_token
SHOPIFY_API_VERSION=2026-07
SHOPIFY_API_SECRET=optional_webhook_secret
```

The connector currently performs a deliberately bounded live snapshot of recent products, customers and orders. This keeps the portfolio demo understandable and avoids pretending that a small local app is already a production data warehouse.

Typical read access required depends on your app configuration and the queries you enable. Keep access tokens on the backend only; never put them in browser JavaScript or commit them to Git.

### Production-scale Shopify history

For a real merchant with large order/product volume, move historical backfill to Shopify GraphQL bulk operations, then keep the local model current through scheduled syncs and registered webhooks. Add retry queues, reconciliation, observability and durable job state.

## Optional AI setup

The local rule-based brief works without AI credentials. To enable an OpenAI model:

```env
OPENAI_API_KEY=your_key
OPENAI_MODEL=an_available_model_for_your_account
```

If a provider request fails, the dashboard can still use the deterministic evidence-based rules.

## Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Runtime / connection modes |
| GET | `/api/dashboard?days=30` | KPI and trend payload |
| GET | `/api/orders` | Order operations queue |
| GET | `/api/orders/:id` | Order drill-down |
| GET | `/api/inventory?days=30` | Inventory health |
| GET | `/api/customers` | Customer segmentation |
| GET | `/api/data-quality` | Data quality + sync history |
| GET | `/api/insights?days=30` | Evidence-grounded business brief |
| POST | `/api/shopify/test` | Test configured Shopify connection |
| POST | `/api/shopify/sync` | Run bounded live snapshot sync |
| POST | `/api/demo/reset` | Restore synthetic demo dataset |
| POST | `/webhooks/shopify` | HMAC-ready webhook receiver |

## Tests

```bash
python -m unittest discover -s tests -v
```

## Security / production notes

This is a portfolio MVP, not a ready-to-install public Shopify App. Before production use, add authentication and organization isolation, proper Shopify OAuth/install flow, encrypted secret storage, CSRF protections where applicable, rate limiting, webhook registration and replay protection, background jobs, PostgreSQL or equivalent, backups, observability, privacy/data-retention controls, and formal handling of Shopify protected customer data requirements.

## Why this portfolio project is useful

It demonstrates the exact product-building skills behind modern ecommerce internal-tool work: translating business questions into usable interfaces, integrating APIs, calculating trustworthy metrics, surfacing exceptions instead of just charts, and adding AI only where it improves decisions.
