#!/usr/bin/env python3
"""
Odoo MCP Server — AI Employee Gold Tier
Exposes Odoo Community accounting via XML-RPC as MCP tools.

Usage (stdio transport, called by Claude Code):
    uv run odoo_mcp.py

Environment variables:
    ODOO_URL       http://localhost:8069
    ODOO_DB        odoo
    ODOO_USER      admin
    ODOO_PASSWORD  admin

Odoo must be running: docker compose up -d
"""

import json
import os
import sys
import xmlrpc.client
from datetime import date, datetime, timedelta
from mcp.server.fastmcp import FastMCP

# ── Config ─────────────────────────────────────────────────────────────────────

ODOO_URL = os.getenv("ODOO_URL", "http://localhost:8069")
ODOO_DB = os.getenv("ODOO_DB", "odoo")
ODOO_USER = os.getenv("ODOO_USER", "admin")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "admin")

mcp = FastMCP("odoo-accounting")


# ── Odoo XML-RPC helpers ───────────────────────────────────────────────────────

def _get_uid() -> tuple[xmlrpc.client.ServerProxy, int]:
    """Authenticate and return (models_proxy, uid)."""
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise RuntimeError(f"Odoo auth failed for user '{ODOO_USER}'. Check credentials and that Odoo is running.")
    models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)
    return models, uid


def _execute(model: str, method: str, *args, **kwargs):
    """Execute an Odoo model method via XML-RPC."""
    models, uid = _get_uid()
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)


# ── MCP Tools ─────────────────────────────────────────────────────────────────


@mcp.tool()
def check_odoo_connection() -> str:
    """Check if Odoo is reachable and authentication works. Use this first."""
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
        version = common.version()
        models, uid = _get_uid()
        return json.dumps({
            "status": "connected",
            "odoo_version": version.get("server_version", "unknown"),
            "uid": uid,
            "url": ODOO_URL,
            "db": ODOO_DB,
        })
    except Exception as e:
        return json.dumps({"status": "error", "error": str(e)})


@mcp.tool()
def list_customers(limit: int = 20, search: str = "") -> str:
    """
    List customers (res.partner with customer_rank > 0).
    Args:
        limit: max records (default 20)
        search: optional name filter
    """
    try:
        domain = [("customer_rank", ">", 0)]
        if search:
            domain.append(("name", "ilike", search))
        records = _execute(
            "res.partner", "search_read",
            domain,
            fields=["id", "name", "email", "phone", "street", "city", "customer_rank"],
            limit=limit,
        )
        return json.dumps({"count": len(records), "customers": records})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def create_customer(name: str, email: str = "", phone: str = "", street: str = "", city: str = "") -> str:
    """
    Create a new customer in Odoo.
    Args:
        name: customer full name (required)
        email: email address
        phone: phone number
        street: street address
        city: city
    """
    try:
        vals = {
            "name": name,
            "customer_rank": 1,
            "is_company": False,
        }
        if email:
            vals["email"] = email
        if phone:
            vals["phone"] = phone
        if street:
            vals["street"] = street
        if city:
            vals["city"] = city
        partner_id = _execute("res.partner", "create", vals)
        return json.dumps({"status": "created", "partner_id": partner_id, "name": name})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_invoices(status: str = "all", limit: int = 20) -> str:
    """
    List customer invoices.
    Args:
        status: 'draft', 'posted' (confirmed), 'paid', 'cancel', or 'all'
        limit: max records (default 20)
    """
    try:
        domain = [("move_type", "=", "out_invoice")]
        if status != "all":
            state_map = {"draft": "draft", "posted": "posted", "paid": "posted", "cancel": "cancel"}
            domain.append(("state", "=", state_map.get(status, status)))
            if status == "paid":
                domain.append(("payment_state", "=", "paid"))
        records = _execute(
            "account.move", "search_read",
            domain,
            fields=["id", "name", "partner_id", "amount_total", "amount_residual",
                    "state", "payment_state", "invoice_date", "invoice_date_due"],
            limit=limit,
            order="invoice_date desc",
        )
        return json.dumps({"count": len(records), "invoices": records})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def create_invoice(
    customer_name: str,
    description: str,
    amount: float,
    due_days: int = 30,
) -> str:
    """
    Create a customer invoice in Odoo (draft state).
    Args:
        customer_name: exact name of existing customer (will search)
        description: product/service description for the invoice line
        amount: invoice total amount (in company currency)
        due_days: payment due in X days from today (default 30)
    """
    try:
        # Find customer
        partners = _execute(
            "res.partner", "search_read",
            [("name", "ilike", customer_name), ("customer_rank", ">", 0)],
            fields=["id", "name"],
            limit=1,
        )
        if not partners:
            return json.dumps({"error": f"Customer '{customer_name}' not found. Create them first."})

        partner = partners[0]
        today = date.today().isoformat()
        due_date = (date.today() + timedelta(days=due_days)).isoformat()

        # Find default income account
        accounts = _execute(
            "account.account", "search_read",
            [("account_type", "in", ["income", "income_other"])],
            fields=["id", "code", "name"],
            limit=1,
        )
        account_id = accounts[0]["id"] if accounts else False

        invoice_vals = {
            "move_type": "out_invoice",
            "partner_id": partner["id"],
            "invoice_date": today,
            "invoice_date_due": due_date,
            "invoice_line_ids": [
                (0, 0, {
                    "name": description,
                    "quantity": 1.0,
                    "price_unit": amount,
                    "account_id": account_id,
                })
            ],
        }
        invoice_id = _execute("account.move", "create", invoice_vals)
        return json.dumps({
            "status": "created",
            "invoice_id": invoice_id,
            "customer": partner["name"],
            "amount": amount,
            "due_date": due_date,
            "note": "Invoice is in 'draft' state. Use confirm_invoice to post it (requires approval).",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def confirm_invoice(invoice_id: int) -> str:
    """
    Confirm (post) a draft invoice. Only call after human approval.
    Args:
        invoice_id: the Odoo invoice ID returned by create_invoice
    """
    try:
        _execute("account.move", "action_post", [invoice_id])
        records = _execute(
            "account.move", "search_read",
            [("id", "=", invoice_id)],
            fields=["name", "state", "amount_total", "payment_state"],
        )
        return json.dumps({"status": "confirmed", "invoice": records[0] if records else {}})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def record_expense(
    description: str,
    amount: float,
    vendor_name: str = "General Vendor",
    expense_date: str = "",
) -> str:
    """
    Record a business expense (vendor bill) in Odoo.
    Args:
        description: what the expense is for
        amount: expense amount
        vendor_name: supplier/vendor name (will create if not found)
        expense_date: YYYY-MM-DD, defaults to today
    """
    try:
        if not expense_date:
            expense_date = date.today().isoformat()

        # Find or create vendor
        vendors = _execute(
            "res.partner", "search_read",
            [("name", "ilike", vendor_name)],
            fields=["id", "name"],
            limit=1,
        )
        if vendors:
            vendor_id = vendors[0]["id"]
        else:
            vendor_id = _execute("res.partner", "create", {
                "name": vendor_name,
                "supplier_rank": 1,
            })

        # Find expense account
        accounts = _execute(
            "account.account", "search_read",
            [("account_type", "in", ["expense", "expense_depreciation"])],
            fields=["id", "name"],
            limit=1,
        )
        account_id = accounts[0]["id"] if accounts else False

        bill_vals = {
            "move_type": "in_invoice",
            "partner_id": vendor_id,
            "invoice_date": expense_date,
            "invoice_line_ids": [
                (0, 0, {
                    "name": description,
                    "quantity": 1.0,
                    "price_unit": amount,
                    "account_id": account_id,
                })
            ],
        }
        bill_id = _execute("account.move", "create", bill_vals)
        return json.dumps({
            "status": "created",
            "bill_id": bill_id,
            "vendor": vendor_name,
            "amount": amount,
            "note": "Expense bill created in draft state.",
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_financial_summary(period: str = "this_month") -> str:
    """
    Get a financial summary: revenue, expenses, outstanding invoices.
    Args:
        period: 'this_month', 'last_month', 'this_year', or 'all'
    """
    try:
        today = date.today()
        if period == "this_month":
            date_from = today.replace(day=1).isoformat()
            date_to = today.isoformat()
        elif period == "last_month":
            first_of_month = today.replace(day=1)
            last_month_end = first_of_month - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            date_from = last_month_start.isoformat()
            date_to = last_month_end.isoformat()
        elif period == "this_year":
            date_from = today.replace(month=1, day=1).isoformat()
            date_to = today.isoformat()
        else:
            date_from = None
            date_to = None

        # Revenue (posted customer invoices)
        rev_domain = [("move_type", "=", "out_invoice"), ("state", "=", "posted")]
        if date_from:
            rev_domain.append(("invoice_date", ">=", date_from))
            rev_domain.append(("invoice_date", "<=", date_to))
        invoices = _execute("account.move", "search_read", rev_domain,
                            fields=["amount_total", "amount_residual", "payment_state"])
        total_revenue = sum(i["amount_total"] for i in invoices)
        total_paid = sum(i["amount_total"] for i in invoices if i["payment_state"] == "paid")
        total_outstanding = sum(i["amount_residual"] for i in invoices if i["amount_residual"] > 0)

        # Expenses (posted vendor bills)
        exp_domain = [("move_type", "=", "in_invoice"), ("state", "=", "posted")]
        if date_from:
            exp_domain.append(("invoice_date", ">=", date_from))
            exp_domain.append(("invoice_date", "<=", date_to))
        bills = _execute("account.move", "search_read", exp_domain,
                         fields=["amount_total"])
        total_expenses = sum(b["amount_total"] for b in bills)

        # Overdue invoices
        overdue_domain = [
            ("move_type", "=", "out_invoice"),
            ("state", "=", "posted"),
            ("payment_state", "!=", "paid"),
            ("invoice_date_due", "<", today.isoformat()),
        ]
        overdue = _execute("account.move", "search_read", overdue_domain,
                           fields=["name", "partner_id", "amount_residual", "invoice_date_due"])

        return json.dumps({
            "period": period,
            "date_from": date_from,
            "date_to": date_to,
            "revenue": {
                "total_invoiced": round(total_revenue, 2),
                "total_paid": round(total_paid, 2),
                "total_outstanding": round(total_outstanding, 2),
                "invoice_count": len(invoices),
            },
            "expenses": {
                "total": round(total_expenses, 2),
                "bill_count": len(bills),
            },
            "net_profit": round(total_paid - total_expenses, 2),
            "overdue_invoices": {
                "count": len(overdue),
                "total_amount": round(sum(o["amount_residual"] for o in overdue), 2),
                "details": overdue[:5],  # top 5
            },
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def list_products(limit: int = 20, search: str = "") -> str:
    """
    List products/services available in Odoo.
    Args:
        limit: max records
        search: name filter
    """
    try:
        domain = [("sale_ok", "=", True)]
        if search:
            domain.append(("name", "ilike", search))
        records = _execute(
            "product.template", "search_read",
            domain,
            fields=["id", "name", "list_price", "type", "description"],
            limit=limit,
        )
        return json.dumps({"count": len(records), "products": records})
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def create_product(name: str, price: float, product_type: str = "service", description: str = "") -> str:
    """
    Create a new product or service in Odoo.
    Args:
        name: product name
        price: sales price
        product_type: 'service', 'consu' (consumable), or 'product' (storable)
        description: optional description
    """
    try:
        vals = {
            "name": name,
            "list_price": price,
            "type": product_type,
            "sale_ok": True,
        }
        if description:
            vals["description"] = description
        product_id = _execute("product.template", "create", vals)
        return json.dumps({"status": "created", "product_id": product_id, "name": name, "price": price})
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
