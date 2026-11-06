# EL-GAS Refilling Station Management System - Tkinter GUI + REST API

## Run the system
1. Open this folder in VS Code.
2. Install packages: `pip install -r requirements.txt`
3. Terminal 1: `python app.py` (keep it running; this starts the Flask JSON API).
4. Terminal 2: `python gui.py` (opens the Tkinter desktop GUI).

Login: `Elgas` / `Elgas123`

## Main features
- Dashboard: Total Customers, Total Refills, Total Kilograms and Total Sales for the selected day (dashboard defaults to today).
- Customer refill record: one customer record can contain multiple tank sizes and quantities in a single transaction.
- CRUD: Add, view, search, update and delete customer refill records.
- Payment status: Paid / Unpaid only.
- Price management: update the current price for each tank size.
- Sales report: daily total customers, refill quantities, kilograms, sales and Paid/Unpaid summary.
- Server-side validation and automatic total calculation.

## API endpoints
| Operation | Method | Endpoint |
|---|---|---|
| Create customer refill | POST | `/api/transactions` |
| List/search records | GET | `/api/transactions` |
| View one record | GET | `/api/transactions/<id>` |
| Update record | PUT | `/api/transactions/<id>` |
| Delete record | DELETE | `/api/transactions/<id>` |
| View tank sizes and prices | GET | `/api/prices` |
| Update tank price | PUT | `/api/prices/<size>` |
| Daily summary | GET | `/api/reports/summary?date=YYYY-MM-DD` |

## Tank record format
A single customer transaction accepts several tank lines:
`{"customer_name":"Sample Customer","payment_status":"Paid","items":[{"size_kg":11,"quantity":2},{"size_kg":5,"quantity":1}]}`

## Notes
- Existing database records are preserved. The app automatically adds the `payment_status` field to an existing database; historical records default to Paid.
- Legacy payment method fields are removed automatically during database initialization. Existing transaction records and payment statuses are preserved.
- Tank prices are sample placeholders. Set the actual approved prices before real use.
- Customer names accept letters and spaces only; tank quantities must be whole numbers greater than 0. An unchanged update is rejected with a validation message.
