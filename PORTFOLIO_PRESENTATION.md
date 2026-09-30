# Shopify AI Commerce Command Center

## Portfolio title
**Shopify AI Commerce Command Center — Sales, Inventory & Customer Intelligence**

## One-line hook
An owner-friendly internal commerce workspace that turns Shopify data into sales trends, order exceptions, inventory risk, customer segments, and evidence-grounded AI recommendations.

## Problem
E-commerce teams often answer operational questions by exporting multiple Shopify reports and maintaining spreadsheets. Sales, orders, inventory, customer behavior, and data-quality issues end up separated, which slows decisions and hides exceptions.

## Solution
Commerce Command combines a Shopify-ready data connector with a local metric engine and a purpose-built web workspace. The dashboard calculates KPIs from stored records, surfaces operational exceptions, and gives an optional AI advisor a controlled metric payload so the AI interprets numbers instead of inventing them.

## Core workflow
Shopify GraphQL / demo data → SQLite snapshot → metric engine → sales + order + inventory + customer views → evidence pack → AI business brief.

## Screens to show in Upwork
1. **Business Pulse** — sales trend, KPIs, action queue, top products, channel mix.
2. **Order Ops** — payment + fulfillment states with aging and order drill-down.
3. **Inventory Control** — velocity, days of cover, reorder thresholds and explicit UNKNOWN data states.
4. **Customer Economics** — VIP, loyal, repeat, new and at-risk segments.
5. **AI Brief** — prioritized insights with the exact metric evidence visible beside them.
6. **Data & Integration** — Shopify connector state, quality score and sync history.

## Technology
Python · SQLite · HTML · CSS · JavaScript · Shopify GraphQL Admin API-ready connector · optional OpenAI Responses API · HMAC-ready Shopify webhook endpoint.

## Truthful demo positioning
This repository is a portfolio/internal-tool MVP. Demo mode uses synthetic commerce data. Live Shopify sync only activates when the owner supplies valid Admin API credentials and scopes. Large-store production sync should use Shopify bulk operations, scheduled ingestion, webhook registration, durable jobs, authentication and a production database.
