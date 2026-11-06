"""Run: python test_api.py   Prints the testing table for the documentation (Program Testing)."""
import os
import tempfile

from elgas import create_app

app = create_app(os.path.join(tempfile.mkdtemp(), "test.db"))
c = app.test_client()
results = []


def check(case, expected, got, want, extra=True):
    results.append((len(results) + 1, case, expected, got, "Pass" if got == want and extra else "FAIL"))


two_lines = {"customer_name": "Juan Dela Cruz", "payment_status": "Paid",
             "items": [{"size_kg": 11, "quantity": 2}, {"size_kg": 22, "quantity": 1}]}

# LOGIN
guest = app.test_client()
r = guest.get("/api/transactions"); check("API without login", "401", r.status_code, 401)
r = guest.get("/history"); check("Page without login goes to login page", "302, /login", r.status_code, 302, r.headers["Location"].endswith("/login"))
r = guest.post("/api/login", json={"email": "Elgas", "password": "wrong"}); check("Login with wrong password", "401", r.status_code, 401)
r = guest.get("/api/transactions", headers={"X-API-Key": "elgas-demo-key"}); check("API with X-API-Key", "200", r.status_code, 200)
r = c.post("/api/login", json={"email": "Elgas", "password": "Elgas123"}); check("Login with correct password", "200", r.status_code, 200)

# CREATE
r = c.post("/api/transactions", json=two_lines); j = r.get_json()
check("Create refill (2 x 11 kg + 1 x 22 kg)", "201, 3 tanks, 44 kg, total 5200", r.status_code, 201,
      j["tank_count"] == 3 and j["total_kg"] == 44 and j["total"] == 5200 and len(j["items"]) == 2)
tid = j["id"]
r = c.post("/api/transactions", json={**two_lines, "customer_name": ""}); check("Create with empty name", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**two_lines, "items": []}); check("Create with no tanks", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**two_lines, "items": [{"size_kg": 11, "quantity": 0}]}); check("Create with quantity 0", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**two_lines, "items": [{"size_kg": -11, "quantity": 1}]}); check("Create with negative size", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**two_lines, "items": [{"size_kg": 13, "quantity": 1}]}); check("Create with size not in price list", "400", r.status_code, 400)
r = c.post("/api/transactions", data="not json", content_type="text/plain"); check("Create without JSON body", "400", r.status_code, 400)
r = c.post("/api/transactions", json={"customer_name": "Ana", "items": [{"size_kg": 11, "quantity": 1}, {"size_kg": 11, "quantity": 2}]})
check("Same size twice is merged", "201, 1 line, 3 tanks", r.status_code, 201, len(r.get_json()["items"]) == 1 and r.get_json()["tank_count"] == 3)
c.post("/api/transactions", json={"customer_name": "Maria Santos", "payment_status": "Unpaid", "items": [{"size_kg": 50, "quantity": 1}]})

# READ, SEARCH, SORT
r = c.get("/api/transactions"); check("List all transactions", "200, 3 records", r.status_code, 200, r.get_json()["count"] == 3)
r = c.get("/api/transactions?search=maria"); check("Search 'maria'", "200, 1 record", r.status_code, 200, r.get_json()["count"] == 1)
r = c.get("/api/transactions?sort=total&order=desc"); check("Sort by total, highest first", "200, first total 5909", r.status_code, 200, r.get_json()["transactions"][0]["total"] == 5909)
r = c.get("/api/transactions?sort=password"); check("Sort by invalid field", "400", r.status_code, 400)
r = c.get("/api/transactions?date=31-10-2026"); check("Filter with bad date", "400", r.status_code, 400)
r = c.get(f"/api/transactions/{tid}"); check("Read one transaction", "200", r.status_code, 200, r.get_json()["customer_name"] == "Juan Dela Cruz")
r = c.get("/api/transactions/9999"); check("Read missing transaction", "404", r.status_code, 404)

# UPDATE
r = c.put(f"/api/transactions/{tid}", json={"items": [{"size_kg": 11, "quantity": 1}, {"size_kg": 22, "quantity": 1}]})
check("Fix tank count (2 x 11 became 1 x 11)", "200, total 3900", r.status_code, 200, r.get_json()["total"] == 3900)
r = c.put(f"/api/transactions/{tid}", json={"payment_status": "Unpaid", "customer_name": "Juan Dela Cruz Jr"})
check("Change payment status and name", "200", r.status_code, 200, r.get_json()["payment_status"] == "Unpaid" and r.get_json()["total"] == 3900)
c.put("/api/prices/11", json={"price": 1400})
r = c.put(f"/api/transactions/{tid}", json={"items": [{"size_kg": 11, "quantity": 2}, {"size_kg": 22, "quantity": 1}]})
check("Edit after price change keeps the old price of that day", "200, total 5200 (not 5400)", r.status_code, 200, r.get_json()["total"] == 5200)
r = c.put(f"/api/transactions/{tid}", json={"items": [{"size_kg": 11, "quantity": 2}, {"size_kg": 50, "quantity": 1}]})
check("New size added to old record uses current price list", "200, total 8509", r.status_code, 200, r.get_json()["total"] == 2 * 1300 + 5909)
r = c.put(f"/api/transactions/{tid}", json={}); check("Update with empty body", "400", r.status_code, 400)
r = c.put("/api/transactions/9999", json={"customer_name": "X"}); check("Update missing transaction", "404", r.status_code, 404)
c.put("/api/prices/11", json={"price": 1300})

# PRICE LIST
r = c.get("/api/prices"); check("Read price list", "200, 6 sizes", r.status_code, 200, len(r.get_json()["prices"]) == 6)
r = c.put("/api/prices/22", json={"price": 2700}); check("Change price of 22 kg", "200", r.status_code, 200, r.get_json()["price"] == 2700)
r = c.put("/api/prices/22", json={"price": -5}); check("Price must be above 0", "400", r.status_code, 400)
r = c.put("/api/prices/99", json={"price": 100}); check("Price for unknown size", "404", r.status_code, 404)

# REPORT
r = c.get("/api/reports/summary"); d = r.get_json()
check("Daily summary report", "200, 3 refills, payment status summary", r.status_code, 200, d["day"]["refills"] == 3 and len(d["by_payment_status"]) >= 2)
r = c.get("/api/reports/summary?date=bad"); check("Report with bad date", "400", r.status_code, 400)

# MORE VALIDATION
ok = {"customer_name": "Pedro", "items": [{"size_kg": 11, "quantity": 1}]}
r = c.post("/api/transactions", json={**ok, "customer_name": "12345"}); check("Name with no letters", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "customer_name": "A" * 61}); check("Name longer than 60 characters", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "customer_name": 123}); check("Name that is not text", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "customer_name": "  Rosa   dela   Cruz  "})
check("Extra spaces in name are cleaned", "201, 'Rosa dela Cruz'", r.status_code, 201, r.get_json()["customer_name"] == "Rosa dela Cruz")
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": "11", "quantity": 1}]}); check("Size sent as text", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": 11, "quantity": 1.5}]}); check("Quantity with decimals", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": 11, "quantity": 101}]}); check("Quantity above 100 is accepted when positive", "201", r.status_code, 201)
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": 11, "quantity": True}]}); check("Quantity true/false", "400", r.status_code, 400)
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": 11, "quantity": 60}, {"size_kg": 11, "quantity": 60}]}); check("Same size quantities are merged", "201", r.status_code, 201)
r = c.post("/api/transactions", json={**ok, "items": [{"size_kg": 11, "quantity": 1}] * 11}); check("More than 10 tank lines", "400", r.status_code, 400)
r = c.post("/api/transactions", json=[1, 2, 3]); check("JSON body that is a list", "400", r.status_code, 400)
r = c.post("/api/transactions", data="{bad json", content_type="application/json"); check("Broken JSON", "400", r.status_code, 400)
r = c.post("/api/transactions", data="x" * 200000, content_type="application/json"); check("Request body too large", "413", r.status_code, 413)
r = c.get("/api/transactions/-1"); check("Negative id", "404", r.status_code, 404)
r = c.get("/api/transactions?search=" + "a" * 61); check("Search text too long", "400", r.status_code, 400)
r = c.get("/api/transactions?page=0"); check("Page 0", "400", r.status_code, 400)
r = c.get("/api/transactions?per_page=500"); check("Too many per page", "400", r.status_code, 400)
r = c.get("/api/transactions?page=abc"); check("Page is not a number", "400", r.status_code, 400)
r = c.get("/api/transactions?per_page=1&page=2"); j = r.get_json()
check("Pages: second page of 1 per page", "200, 1 record, pages = records", r.status_code, 200, len(j["transactions"]) == 1 and j["pages"] == j["count"])
r = c.get("/api/transactions?search=%25"); check("Search for % only finds names with %", "200, 0 records", r.status_code, 200, r.get_json()["count"] == 0)
r = c.put("/api/prices/22", json={"price": "abc"}); check("Price as text", "400", r.status_code, 400)
r = c.put("/api/prices/22", json={"price": 1e9}); check("Price too high", "400", r.status_code, 400)
r = c.post("/api/login", json={"email": "Elgas"}); check("Login without password", "400", r.status_code, 400)

# WEEKLY REPORT
from datetime import date, timedelta
today = date.today(); first = today - timedelta(days=6)
r = c.get(f"/api/reports/range?start={first}&end={today}"); j = r.get_json()
check("Weekly report lists 7 days", "200, 7 days", r.status_code, 200, len(j["days"]) == 7)
check("Weekly total equals the sum of the days", "same sales", r.status_code, 200, abs(j["total"]["sales"] - sum(d["sales"] for d in j["days"])) < 0.01 and j["total"]["refills"] >= 1)
r = c.get(f"/api/reports/range?start={today}&end={first}"); check("Report with end before start", "400", r.status_code, 400)
r = c.get("/api/reports/range?start=2026-01-01&end=2026-12-31"); check("Report range longer than 93 days", "400", r.status_code, 400)
r = c.get("/api/reports/range?start=2026-01-01"); check("Report without end date", "400", r.status_code, 400)
r = c.get("/api/reports/range?start=abc&end=def"); check("Report with bad dates", "400", r.status_code, 400)
r = c.get("/reports"); check("Reports page opens", "200", r.status_code, 200)

# DELETE
r = c.delete(f"/api/transactions/{tid}"); check("Delete transaction", "204", r.status_code, 204)
r = c.get(f"/api/transactions/{tid}"); check("Deleted record is gone", "404", r.status_code, 404)
r = c.delete(f"/api/transactions/{tid}"); check("Delete again", "404", r.status_code, 404)

# PAGES
for path, name in [("/dashboard", "Dashboard"), ("/new", "New Refill"), ("/history", "History"), ("/prices", "Price List")]:
    r = c.get(path); check(f"{name} page opens", "200", r.status_code, 200)
r = c.get("/transactions/2"); check("Transaction detail page opens", "200", r.status_code, 200)
r = c.get("/receipt/2"); check("Receipt page opens", "200", r.status_code, 200, b"EL-GAS" in r.data)
r = c.post("/api/logout"); check("Logout", "200", r.status_code, 200)
r = c.get("/api/transactions"); check("API after logout", "401", r.status_code, 401)

print(f"{'No.':<4}{'Test case':<58}{'Expected':<42}{'Status':<8}Result")
for n, case, exp, got, res in results:
    print(f"{n:<4}{case:<58}{exp:<42}{got:<8}{res}")
fails = [r for r in results if r[4] != "Pass"]
print(f"\n{len(results) - len(fails)}/{len(results)} passed")
raise SystemExit(1 if fails else 0)
