"""Input validation. Every function returns (clean_data, errors); errors is empty when the input is valid.
The desktop client and API both validate input; the server must never trust client input."""
import math
import re
import unicodedata
from datetime import datetime

from .db import PAYMENT_STATUSES

MAX_REPORT_DAYS = 92  # longest date range the weekly/monthly report accepts


def to_number(value):
    """Accept real JSON numbers only: no text like "5", no true/false, no NaN or infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError
    return float(value)


def parse_date(text):
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date()
    except ValueError:
        return None


def clean_name(value):
    """1 to 60 characters, at least one letter, no control characters. Extra spaces are removed."""
    if not isinstance(value, str):
        return None
    name = re.sub(r"\s+", " ", value).strip()
    if not 1 <= len(name) <= 60 or not all(ch.isalpha() or ch.isspace() for ch in name) or not any(ch.isalpha() for ch in name):
        return None
    return name


def parse_items(raw):
    """Validate the tank lines: [{"size_kg": 11, "quantity": 2}, ...]. The same size twice is merged."""
    if not isinstance(raw, list) or not raw:
        return None, "Add at least one tank size."
    if len(raw) > 10:
        return None, "At most 10 tank lines."
    merged = {}
    for line in raw:
        if not isinstance(line, dict):
            return None, "Each tank line must be an object with size_kg and quantity."
        try:
            size, qty = to_number(line.get("size_kg")), to_number(line.get("quantity"))
            if not 0 < size <= 100 or qty != int(qty) or qty < 1:
                raise ValueError
        except (TypeError, ValueError):
            return None, "Each line needs a valid tank size and a whole-number quantity greater than 0."
        key = round(size, 2)
        merged[key] = merged.get(key, 0) + int(qty)
        return [{"size_kg": s, "quantity": q} for s, q in sorted(merged.items())], None


def validate_transaction(data, partial=False):
    clean, errors = {}, {}
    if "customer_name" in data or not partial:
        name = clean_name(data.get("customer_name"))
        if name:
            clean["customer_name"] = name
        else:
            errors["customer_name"] = "Required. 1 to 60 characters with at least one letter."
    if "payment_status" in data or not partial:
        status = data.get("payment_status", "Paid")
        if status in PAYMENT_STATUSES:
            clean["payment_status"] = status
        else:
            errors["payment_status"] = f"Must be one of: {', '.join(PAYMENT_STATUSES)}."
    if "items" in data or not partial:
        items, err = parse_items(data.get("items"))
        if err:
            errors["items"] = err
        else:
            clean["items"] = items
    return clean, errors


def validate_price_update(data):
    clean, errors = {}, {}
    if "price" in data:
        try:
            price = to_number(data["price"])
            if not 0 < price <= 100000:
                raise ValueError
            clean["price"] = round(price, 2)
        except (TypeError, ValueError):
            errors["price"] = "Must be a number greater than 0 and at most 100,000."
    return clean, errors


def validate_date_range(start_text, end_text):
    """Returns (start, end, error_message)."""
    start, end = parse_date(start_text), parse_date(end_text)
    if not start or not end:
        return None, None, "start and end are required, written as YYYY-MM-DD."
    if end < start:
        return None, None, "end must be the same day or later than start."
    if (end - start).days > MAX_REPORT_DAYS:
        return None, None, f"The range can be at most {MAX_REPORT_DAYS + 1} days."
    return start, end, None
