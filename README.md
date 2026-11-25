# Dashboard — E-Commerce Analytics & BI Platform

Production-quality e-commerce analytics dashboard. Connect databases, upload CSV/Excel files, or integrate Shopify/WooCommerce to get KPIs, charts, insights, and alerts.

**PostgreSQL database name: `dashboard`**

## Stack

- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts, TanStack Table, React Router
- **Backend:** Python, FastAPI, SQLAlchemy 2.x, Pydantic, Pandas, Alembic
- **Database:** PostgreSQL (`dashboard`)

## Quick Start

### 1. Start PostgreSQL

```bash
docker compose up -d
```

This creates database **`dashboard`** with user `dashboard_user` / password `dashboard_pass`.

### 2. Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example .env   # or cp on macOS/Linux
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Database Configuration

All configs use database name **`dashboard`**:

| Setting | Value |
|---------|-------|
| Database | `dashboard` |
| User | `dashboard_user` |
| Password | `dashboard_pass` |
| Port | `5432` |
| Connection URL | `postgresql://dashboard_user:dashboard_pass@localhost:5432/dashboard` |

## Features

- User registration & authentication (Admin / Analyst / Viewer roles)
- Multi-tenant business isolation
- Connect Data: PostgreSQL, MySQL, SQL Server, CSV/Excel, Shopify, WooCommerce
- Automatic file detection & column mapping
- Data validation before import
- Executive dashboard with KPIs and charts
- Sales, Product, Customer, RFM, Inventory, Marketing analytics
- Automated insights & alert center
- Local database connector agent for remote-hosted dashboards
- Encrypted credential storage (passwords never returned to frontend)

## Sample Data

Upload files from `sample-data/` via Connect Data → CSV / Excel.

## Local Connector

For databases on your local machine when the dashboard runs remotely:

```bash
pip install httpx psycopg2-binary
python connector/agent.py --agent-token YOUR_TOKEN --username dashboard_user --password dashboard_pass --database dashboard
```

## Project Structure

```
Dashboard/
├── backend/app/          # FastAPI application
├── frontend/             # React dashboard
├── connector/            # Local DB connector agent
├── sample-data/          # Demo CSV files
└── docker-compose.yml    # PostgreSQL (database: dashboard)
```
