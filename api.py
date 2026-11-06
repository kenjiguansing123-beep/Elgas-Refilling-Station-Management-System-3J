"""REST API (JSON). Create = POST, Read = GET, Update = PUT, Delete = DELETE."""
import math
from datetime import datetime

from flask import Blueprint, jsonify, request, session

from . import services as svc
from .auth import api_guard, check_login
from .db import get_db, now
from .validation import parse_date, validate_date_range, validate_price_update, validate_transaction

api_bp = Blueprint("api", __name__, url_prefix="/api")
api_bp.before_request(api_guard)

SORT_FIELDS = {"id", "created_at", "customer_name", "tank_count", "total_kg", "total", "payment_status"}


def error(message, status, details=None):
    body = {"error": message}
    if details:
        body["details"] = details
    return jsonify(body), status


# ---------------------------------------------------------------- login
@api_bp.post("/login")
def login():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data.get("email") or not data.get("password"):
        return error("email and password are required.", 400)
    if check_login(data.get("email", ""), data.get("password", "")):
        session["user"] = str(data["email"]).strip()
        return jsonify(message="Logged in.", user=session["user"]), 200
    return error("Wrong email or password.", 401)


@api_bp.post("/logout")
def logout():
    session.clear()
    return jsonify(message="Logged out."), 200


# ---------------------------------------------------------------- transactions
def int_arg(name, default, low, high):
    raw = request.args.get(name, "").strip()
    if not raw:
        return default, None
    try:
        value = int(raw)
    except ValueError:
        return None, f"{name} must be a whole number."
    if not low <= value <= high:
        return None, f"{name} must be from {low} to {high}."
    return value, None


@api_bp.get("/transactions")          # READ: list + search + filter + sort + pages
def list_transactions():
    search = request.args.get("search", "").strip()
    date = request.args.get("date", "").strip()
    sort = request.args.get("sort", "id")
    order = "ASC" if request.args.get("order", "desc").lower() == "asc" else "DESC"
    if sort not in SORT_FIELDS:
        return error(f"Invalid sort field. Use one of: {sorted(SORT_FIELDS)}", 400)
    if len(search) > 60:
        return error("search can be at most 60 characters.", 400)
    if date and not parse_date(date):
        return error("date must be YYYY-MM-DD.", 400)
    page, err = int_arg("page", 1, 1, 100000)
    if err:
        return error(err, 400)
    per_page, err = int_arg("per_page", 20, 1, 100)
    if err:
        return error(err, 400)

    where, params = " FROM transactions WHERE 1=1", []
    if search:
        # Numeric exact search matches the derived Customer ID (oldest transaction ID
        # for a customer); this returns every transaction for that customer.
        if search.isdigit():
            where += " AND customer_name IN (SELECT customer_name FROM transactions GROUP BY customer_name HAVING MIN(id)=?)"
            params.append(int(search))
        else:
            where += " AND customer_name LIKE ? ESCAPE '\\'"
            params.append("%" + search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%")
    if date:
        where += " AND substr(created_at,1,10) = ?"
        params.append(date)
    db = get_db()
    total = db.execute("SELECT COUNT(*)" + where, params).fetchone()[0]
    rows = db.execute("SELECT *" + where + f" ORDER BY {sort} {order}, id DESC LIMIT ? OFFSET ?",
                      params + [per_page, (page - 1) * per_page]).fetchall()
    return jsonify(count=total, page=page, per_page=per_page, pages=max(1, math.ceil(total / per_page)),
                   transactions=svc.with_items(rows)), 200


@api_bp.get("/transactions/<int:tid>")  # READ: one
def get_transaction(tid):
    record = svc.get_transaction(tid)
    if not record:
        return error("Transaction not found.", 404)
    return jsonify(record), 200


@api_bp.post("/transactions")         # CREATE
def create_transaction():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("Send a JSON body.", 400)
    clean, errors = validate_transaction(data)
    if errors:
        return error("Validation failed.", 400, errors)
    lines, totals, problem = svc.build_lines(clean["items"])
    if problem:
        return error("Validation failed.", 400, {"items": problem})
    db, stamp = get_db(), now()
    cur = db.execute(
        "INSERT INTO transactions (customer_name, payment_status, tank_count, total_kg, total, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (clean["customer_name"], clean["payment_status"], totals["tank_count"], totals["total_kg"],
         totals["total"], stamp, stamp))
    svc.save_lines(cur.lastrowid, lines)
    db.commit()
    return jsonify(svc.get_transaction(cur.lastrowid)), 201


@api_bp.put("/transactions/<int:tid>")  # UPDATE: name, payment status, tanks (total is recomputed)
def update_transaction(tid):
    current = svc.get_transaction(tid)
    if not current:
        return error("Transaction not found.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return error("Send a JSON body with the fields to change.", 400)
    clean, errors = validate_transaction(data, partial=True)
    if errors:
        return error("Validation failed.", 400, errors)
    if not clean:
        return error("No valid fields to update.", 400)

    name = clean.get("customer_name", current["customer_name"])
    status = clean.get("payment_status", current.get("payment_status", "Paid"))
    totals = {"tank_count": current["tank_count"], "total_kg": current["total_kg"], "total": current["total"]}
    lines = None
    if "items" in clean:
        # a size already in this transaction keeps its price from that day
        locked = {i["size_kg"]: i["unit_price"] for i in current["items"]}
        lines, totals, problem = svc.build_lines(clean["items"], locked)
        if problem:
            return error("Validation failed.", 400, {"items": problem})

    current_items = sorted((round(float(i["size_kg"]), 2), int(i["quantity"])) for i in current["items"])
    proposed_items = current_items if lines is None else sorted((round(float(i["size_kg"]), 2), int(i["quantity"])) for i in lines)
    if name == current["customer_name"] and status == current.get("payment_status", "Paid") and proposed_items == current_items:
        return error("No changes detected. Please update at least one field.", 400)

    db = get_db()
    db.execute("UPDATE transactions SET customer_name=?, payment_status=?, tank_count=?, total_kg=?, total=?, "
               "updated_at=? WHERE id=?",
               (name, status, totals["tank_count"], totals["total_kg"], totals["total"], now(), tid))
    if lines is not None:
        svc.save_lines(tid, lines)
    db.commit()
    return jsonify(svc.get_transaction(tid)), 200


@api_bp.delete("/transactions/<int:tid>")  # DELETE
def delete_transaction(tid):
    db = get_db()
    if not db.execute("SELECT 1 FROM transactions WHERE id=?", (tid,)).fetchone():
        return error("Transaction not found.", 404)
    db.execute("DELETE FROM transaction_items WHERE transaction_id=?", (tid,))
    db.execute("DELETE FROM transactions WHERE id=?", (tid,))
    db.commit()
    return "", 204


# ---------------------------------------------------------------- price list
@api_bp.get("/prices")
def list_prices():
    rows = get_db().execute("SELECT size_kg, price, updated_at FROM price_list ORDER BY size_kg").fetchall()
    return jsonify(prices=[dict(r) for r in rows]), 200


@api_bp.put("/prices/<size>")
def update_price(size):
    try:
        size = round(float(size), 2)
    except ValueError:
        return error("Price not found for that size.", 404)
    db = get_db()
    row = db.execute("SELECT * FROM price_list WHERE size_kg=?", (size,)).fetchone()
    if not row:
        return error("Price not found for that size.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return error("Send a JSON body with a price.", 400)
    clean, errors = validate_price_update(data)
    if errors:
        return error("Validation failed.", 400, errors)
    if not clean:
        return error("No valid fields to update.", 400)
    db.execute("UPDATE price_list SET price=?, updated_at=? WHERE size_kg=?",
               (clean.get("price", row["price"]), now(), size))
    db.commit()
    new = db.execute("SELECT size_kg, price, updated_at FROM price_list WHERE size_kg=?", (size,)).fetchone()
    return jsonify(dict(new)), 200


# ---------------------------------------------------------------- report
@api_bp.get("/reports/summary")        # one day
def summary_report():
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    if not parse_date(date):
        return error("date must be YYYY-MM-DD.", 400)
    return jsonify(svc.day_summary(date)), 200


@api_bp.get("/reports/range")          # week, month, or any date range
def range_report():
    start, end, problem = validate_date_range(request.args.get("start", ""), request.args.get("end", ""))
    if problem:
        return error(problem, 400)
    return jsonify(svc.range_summary(start, end)), 200
