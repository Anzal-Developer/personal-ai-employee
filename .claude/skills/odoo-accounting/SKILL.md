# Skill: odoo-accounting

Interact with the self-hosted Odoo Community accounting system via the Odoo MCP server.

## Prerequisites

1. Odoo must be running: `docker compose up -d` (wait ~60s for first boot)
2. Odoo MCP server must be configured in `.claude/settings.json` (already done)
3. First-time setup: visit http://localhost:8069, create database "odoo", install Accounting module

## Trigger

Use this skill when the user wants to:
- Create, view, or confirm customer invoices
- Record business expenses
- Get a financial summary (revenue, expenses, profit)
- List or create customers/products
- Perform accounting audits

## Available MCP Tools

All tools are exposed via the `odoo` MCP server:

| Tool | Description |
|------|-------------|
| `check_odoo_connection` | Verify Odoo is reachable |
| `list_customers` | List customers with optional search |
| `create_customer` | Add a new customer |
| `list_invoices` | List invoices by status (draft/posted/paid/all) |
| `create_invoice` | Create a customer invoice (draft) |
| `confirm_invoice` | Post a draft invoice (requires approval) |
| `record_expense` | Create a vendor bill / expense |
| `get_financial_summary` | Revenue, expenses, profit for a period |
| `list_products` | List products/services |
| `create_product` | Add a product or service |

## Workflow

### For invoice creation (with HITL):
1. Check connection: `check_odoo_connection`
2. Find or create customer: `list_customers` → `create_customer`
3. Create invoice: `create_invoice` (creates in draft state)
4. Create approval request in `/Pending_Approval/INVOICE_*.md`
5. Human approves → call `confirm_invoice`
6. Log the action

### For financial reporting (autonomous):
1. `get_financial_summary(period="this_month")`
2. Format as readable report
3. Save to `/Done/FINANCE_REPORT_YYYY-MM-DD.md`

### For expense recording:
1. `record_expense(description, amount, vendor_name)`
2. Log the action (approval required to confirm)

## HITL Rules

Per Company_Handbook.md:
- **Autonomous**: `check_odoo_connection`, `list_*`, `get_financial_summary`, `create_*` (draft only)
- **Requires approval**: `confirm_invoice`, any action that posts/confirms financial records

## Odoo Access

- URL: http://localhost:8069
- DB: odoo
- User: admin / admin (change after first login)
- Start: `docker compose up -d`
- Stop: `docker compose down`
- Logs: `docker compose logs -f odoo`

## Example invocations

**"Create an invoice for Acme Corp for $500 consulting"**
1. check_odoo_connection
2. list_customers → find Acme Corp
3. create_invoice(customer_name="Acme Corp", description="Consulting services", amount=500)
4. Create approval file in /Pending_Approval
5. Log action

**"Give me this month's financial summary"**
1. check_odoo_connection
2. get_financial_summary(period="this_month")
3. Format and display results
4. Save report to /Done
