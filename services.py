"""Business logic: prices, totals, and reading/writing transactions with their tank lines."""
from datetime import timedelta

from .db import get_db


def build_lines(parsed_items, locked_prices=None):
    """Attach a unit price to every tank line and compute the totals.

    locked_prices = {size_kg: unit_price} of the transaction being edited: a size that is already in
    the transaction keeps the price of that day, a new size uses the current price list.
    Returns (lines, totals, error_message).
    """
    locked_prices = locked_prices or {}
    db, lines = get_db(), []
    for item in parsed_items:
        size = item["size_kg"]
        if size in locked_prices:
            unit_price = locked_prices[size]
        else:
            row = db.execute("SELECT price FROM price_list WHERE size_kg=?", (size,)).fetchone()
            if not row:
                return None, None, f"{size:g} kg is not in the price list."
            unit_price = row["price"]
        lines.append({"size_kg": size, "quantity": item["quantity"], "unit_price": unit_price,
                      "subtotal": round(unit_price * item["quantity"], 2)})
    totals = {"tank_count": sum(l["quantity"] for l in lines),
              "total_kg": round(sum(l["size_kg"] * l["quantity"] for l in lines), 2),
              "total": round(sum(l["subtotal"] for l in lines), 2)}
    return lines, totals, None


def save_lines(transaction_id, lines):
    db = get_db()
    db.execute("DELETE FROM transaction_items WHERE transaction_id=?", (transaction_id,))
    db.executemany("INSERT INTO transaction_items (transaction_id, size_kg, quantity, unit_price) VALUES (?,?,?,?)",
                   [(transaction_id, l["size_kg"], l["quantity"], l["unit_price"]) for l in lines])


def fetch_lines(ids):
    """{transaction_id: [lines]} for the given ids."""
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = get_db().execute(
        f"SELECT transaction_id, size_kg, quantity, unit_price FROM transaction_items "
        f"WHERE transaction_id IN ({marks}) ORDER BY size_kg", list(ids)).fetchall()
    out = {i: [] for i in ids}
    for r in rows:
        out[r["transaction_id"]].append({"size_kg": r["size_kg"], "quantity": r["quantity"],
                                         "unit_price": r["unit_price"],
                                         "subtotal": round(r["unit_price"] * r["quantity"], 2)})
    return out


def with_items(rows):
    result = [dict(r) for r in rows]
    by_id = fetch_lines([r["id"] for r in result])
    for r in result:
        # Customer ID is the first (oldest) transaction ID for that customer name.
        # This gives repeat transactions by the same customer a consistent ID
        # without discarding existing records or requiring a database reset.
        customer = get_db().execute(
            "SELECT MIN(id) FROM transactions WHERE customer_name = ? COLLATE NOCASE",
            (r["customer_name"],)).fetchone()[0]
        r["customer_id"] = customer
        r["items"] = by_id[r["id"]]
    return result


def get_transaction(tid):
    row = get_db().execute("SELECT * FROM transactions WHERE id=?", (tid,)).fetchone()
    return with_items([row])[0] if row else None


def list_prices():
    rows = get_db().execute("SELECT size_kg, price FROM price_list ORDER BY size_kg").fetchall()
    return [dict(r) for r in rows]


def day_summary(date):
    db = get_db()
    day = db.execute(
        "SELECT COUNT(DISTINCT customer_name) AS customers, COALESCE(SUM(tank_count),0) AS refills, "
        "COALESCE(SUM(total_kg),0) AS kg, COALESCE(SUM(total),0) AS sales "
        "FROM transactions WHERE substr(created_at,1,10)=?", (date,)).fetchone()
    by_status = db.execute(
        "SELECT payment_status, COUNT(*) AS customers, SUM(total) AS amount FROM transactions "
        "WHERE substr(created_at,1,10)=? GROUP BY payment_status ORDER BY payment_status", (date,)).fetchall()
    return {"date": date,
            "day": {k: round(day[k], 2) for k in day.keys()},
            "by_payment_status": [{"payment_status": r["payment_status"], "customers": r["customers"],
                                   "amount": round(r["amount"], 2)} for r in by_status]}


def range_summary(start, end):
    """Sales for every day from start to end (dates), including days with no sales."""
    db, s, e = get_db(), start.isoformat(), end.isoformat()
    rows = db.execute(
        "SELECT substr(created_at,1,10) AS day, COUNT(DISTINCT customer_name) AS customers, SUM(tank_count) AS refills, "
        "SUM(total_kg) AS kg, SUM(total) AS sales FROM transactions "
        "WHERE substr(created_at,1,10) BETWEEN ? AND ? GROUP BY day", (s, e)).fetchall()
    by_day = {r["day"]: r for r in rows}
    days, d = [], start
    while d <= end:
        r = by_day.get(d.isoformat())
        days.append({"date": d.isoformat(), "customers": r["customers"] if r else 0, "refills": r["refills"] if r else 0,
                     "kg": round(r["kg"], 2) if r else 0, "sales": round(r["sales"], 2) if r else 0})
        d += timedelta(days=1)
    by_method = db.execute(
        "SELECT payment_status, COUNT(*) AS customers, SUM(total) AS amount FROM transactions "
        "WHERE substr(created_at,1,10) BETWEEN ? AND ? GROUP BY payment_status ORDER BY payment_status", (s, e)).fetchall()
    return {"start": s, "end": e, "days": days,
            "total": {"customers": sum(x["customers"] for x in days), "refills": sum(x["refills"] for x in days),
                      "kg": round(sum(x["kg"] for x in days), 2), "sales": round(sum(x["sales"] for x in days), 2)},
            "by_payment_status": [{"payment_status": r["payment_status"], "customers": r["customers"],
                                   "amount": round(r["amount"], 2)} for r in by_method]}
