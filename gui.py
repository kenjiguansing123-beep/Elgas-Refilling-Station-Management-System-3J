"""EL-GAS Refilling Station - Tkinter GUI client for the Flask JSON REST API."""
import json
import urllib.request
import urllib.error
import http.cookiejar
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

BASE_URL = "http://127.0.0.1:5000"
API_KEY = "elgas-demo-key"


class APIClient:
    def __init__(self):
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))
        self.logged_in = False

    def request(self, method, path, body=None, params=None):
        url = BASE_URL + path
        if params:
            from urllib.parse import urlencode
            url += "?" + urlencode({k: v for k, v in params.items() if v not in ("", None)})
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url, data=data, method=method,
            headers={"Content-Type": "application/json", "X-API-Key": API_KEY}
        )
        try:
            with self.opener.open(req, timeout=5) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                payload = json.loads(raw) if raw else {}
            except ValueError:
                payload = {"error": raw.decode("utf-8", "replace")}
            return exc.code, payload
        except urllib.error.URLError:
            raise ConnectionError("Cannot connect to the API. Start the server first using: python app.py")


class ElgasGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("EL-GAS REFILLING STATION MANAGEMENT SYSTEM")
        self.root.geometry("1180x740")
        self.root.minsize(1000, 650)
        self.root.configure(bg="#eef2f7")
        self.api = APIClient()
        self.prices = []
        self.selected_id = None
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.style.configure("Treeview", rowheight=28, font=("Segoe UI", 10))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))
        self.style.configure("TButton", font=("Segoe UI", 10), padding=7)
        self.style.configure("Header.TLabel", font=("Segoe UI", 18, "bold"), foreground="#12345a")
        self.show_login()

    def clear(self):
        for child in self.root.winfo_children():
            child.destroy()

    def show_login(self):
        self.clear()
        frame = tk.Frame(self.root, bg="white", padx=45, pady=38, highlightbackground="#cbd5e1", highlightthickness=1)
        frame.place(relx=.5, rely=.5, anchor="center")
        tk.Label(frame, text="EL-GAS", font=("Segoe UI", 30, "bold"), fg="#12345a", bg="white").pack(pady=(0, 3))
        tk.Label(frame, text="REFILLING STATION MANAGEMENT SYSTEM", font=("Segoe UI", 10, "bold"),
                 fg="#52657a", bg="white").pack(pady=(0, 25))
        tk.Label(frame, text="Username", bg="white", anchor="w").pack(fill="x")
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=34).pack(pady=(4, 14), ipady=5)
        tk.Label(frame, text="Password", bg="white", anchor="w").pack(fill="x")
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(frame, textvariable=self.password_var, show="*", width=34)
        self.password_entry.pack(pady=(4, 5), ipady=5)

        self.show_password_var = tk.BooleanVar(value=False)
        def toggle_password_visibility():
            self.password_entry.configure(show="" if self.show_password_var.get() else "*")

        # Use Tk's standard checkbutton so the selected state shows a check mark.
        tk.Checkbutton(
            frame,
            text="Show password",
            variable=self.show_password_var,
            command=toggle_password_visibility,
            indicatoron=True,
            selectcolor="white",
            bg="white",
            activebackground="white",
            fg="#12345a",
            activeforeground="#12345a",
            font=("Segoe UI", 9),
            bd=0,
            highlightthickness=0
        ).pack(anchor="w", pady=(0, 14))
        ttk.Button(frame, text="LOGIN", command=self.login).pack(fill="x")
        self.root.bind("<Return>", lambda event: self.login())

    def login(self):
        try:
            status, data = self.api.request("POST", "/api/login",
                                            {"email": self.email_var.get().strip(),
                                             "password": self.password_var.get()})
            if status == 200:
                self.api.logged_in = True
                self.show_main()
            else:
                messagebox.showerror("Login failed", data.get("error", "Invalid login details."))
        except ConnectionError as exc:
            messagebox.showerror("API connection", str(exc))

    def show_main(self):
        self.root.unbind("<Return>")
        self.clear()
        header = tk.Frame(self.root, bg="#12345a", padx=20, pady=14)
        header.pack(fill="x")
        tk.Label(header, text="EL-GAS REFILLING STATION", bg="#12345a", fg="white",
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(header, text="Management System", bg="#12345a", fg="#dbeafe",
                 font=("Segoe UI", 10)).pack(side="left", padx=15, pady=(8, 0))
        ttk.Button(header, text="Logout", command=self.logout).pack(side="right")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=16, pady=15)
        self.dashboard_tab = ttk.Frame(self.tabs, padding=15)
        self.records_tab = ttk.Frame(self.tabs, padding=15)
        self.prices_tab = ttk.Frame(self.tabs, padding=15)
        self.reports_tab = ttk.Frame(self.tabs, padding=15)
        self.tabs.add(self.dashboard_tab, text="Dashboard")
        self.tabs.add(self.records_tab, text="Refill Records / CRUD")
        self.tabs.add(self.prices_tab, text="Price Management")
        self.tabs.add(self.reports_tab, text="Sales Reports")
        self.build_dashboard()
        self.build_records()
        self.build_prices()
        self.build_reports()
        self.refresh_all()

    def logout(self):
        confirm = messagebox.askyesno(
            "Confirm Logout",
            "Are you sure you want to logout?"
        )
        if not confirm:
            return

        try:
            self.api.request("POST", "/api/logout")
        except Exception:
            pass
        self.show_login()

    def api_call(self, method, path, body=None, params=None):
        try:
            status, data = self.api.request(method, path, body, params)
            if status >= 400:
                details = data.get("details", {}) if isinstance(data, dict) else {}
                msg = data.get("error", "Request failed.")
                if details:
                    msg += "\n" + "\n".join(f"{k}: {v}" for k, v in details.items())
                messagebox.showerror(f"API Error ({status})", msg)
                return None
            return data
        except ConnectionError as exc:
            messagebox.showerror("API connection", str(exc))
            return None

    def build_dashboard(self):
        ttk.Label(self.dashboard_tab, text="Business Overview", style="Header.TLabel").pack(anchor="w", pady=(0, 15))
        cards = ttk.Frame(self.dashboard_tab)
        cards.pack(fill="x")
        self.card_values = {}
        for key, label in [("customers", "TOTAL CUSTOMERS"), ("refills", "TOTAL REFILLS"),
                           ("kg", "TOTAL KILOGRAMS"), ("sales", "TOTAL SALES")]:
            card = tk.Frame(cards, bg="white", padx=22, pady=18, highlightbackground="#d7e0ea", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Label(card, text=label, bg="white", fg="#64748b", font=("Segoe UI", 9, "bold")).pack(anchor="w")
            value = tk.Label(card, text="0", bg="white", fg="#12345a", font=("Segoe UI", 22, "bold"))
            value.pack(anchor="w", pady=(8, 0))
            self.card_values[key] = value
        ttk.Label(self.dashboard_tab, text="Today's sales summary", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(28, 8))
        self.dashboard_info = ttk.Label(self.dashboard_tab, text="Refresh to load today's summary.")
        self.dashboard_info.pack(anchor="w")
        ttk.Button(self.dashboard_tab, text="Refresh Dashboard", command=self.refresh_dashboard).pack(anchor="w", pady=15)

    def build_records(self):
        ttk.Label(self.records_tab, text="Refill Transactions", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        searchbar = ttk.Frame(self.records_tab)
        searchbar.pack(fill="x", pady=(0, 10))
        ttk.Label(searchbar, text="Search customer:").pack(side="left")
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(searchbar, textvariable=self.search_var, width=28)
        search_entry.pack(side="left", padx=7)
        search_entry.bind("<Return>", lambda event: self.refresh_records())
        ttk.Button(searchbar, text="Search", command=self.refresh_records).pack(side="left")
        ttk.Button(searchbar, text="Show All", command=self.clear_search).pack(side="left", padx=5)
        cols = ("id", "date", "customer", "status", "tanks", "kg", "total")
        self.records_tree = ttk.Treeview(self.records_tab, columns=cols, show="headings", height=13)
        headings = [("id","Customer ID",85),("date","Date",150),("customer","Customer",190),
                    ("status","Payment Status",110),("tanks","Total Refills",95),("kg","Total KG",100),("total","Total Amount",130)]
        for col, title, width in headings:
            self.records_tree.heading(col, text=title)
            self.records_tree.column(col, width=width, anchor="center")
        self.records_tree.pack(fill="both", expand=True)
        self.records_tree.bind("<<TreeviewSelect>>", self.on_select_record)
        buttons = ttk.Frame(self.records_tab)
        buttons.pack(fill="x", pady=10)
        ttk.Button(buttons, text="Add New Refill", command=self.add_refill).pack(side="left", padx=(0, 7))
        ttk.Button(buttons, text="View Details", command=self.view_refill).pack(side="left", padx=7)
        ttk.Button(buttons, text="Update Selected", command=self.update_refill).pack(side="left", padx=7)
        ttk.Button(buttons, text="Delete Selected", command=self.delete_refill).pack(side="left", padx=7)
        ttk.Button(buttons, text="Refresh", command=self.refresh_records).pack(side="right")

    def build_prices(self):
        ttk.Label(self.prices_tab, text="LPG Price Management", style="Header.TLabel").pack(anchor="w", pady=(0, 10))
        ttk.Label(self.prices_tab, text="Update the current selling price for each tank size. Existing refill records retain their saved prices.",
                  wraplength=900).pack(anchor="w", pady=(0, 12))
        self.price_tree = ttk.Treeview(self.prices_tab, columns=("size","price","updated"), show="headings", height=12)
        for col, title, width in [("size","Tank Size (KG)",180),("price","Price per Tank (PHP)",220),
                                  ("updated","Last Updated",230)]:
            self.price_tree.heading(col, text=title)
            self.price_tree.column(col, width=width, anchor="center")
        self.price_tree.pack(fill="x")
        row = ttk.Frame(self.prices_tab)
        row.pack(anchor="w", pady=15)
        ttk.Label(row, text="New price (PHP):").pack(side="left")
        self.new_price_var = tk.StringVar()
        ttk.Entry(row, textvariable=self.new_price_var, width=16).pack(side="left", padx=8)
        ttk.Button(row, text="Update Price", command=self.update_price).pack(side="left")
        ttk.Button(row, text="Refresh Prices", command=self.refresh_prices).pack(side="left", padx=8)
        ttk.Label(self.prices_tab, text="Select a tank size to update its current price.",
                  foreground="#52657a").pack(anchor="w", pady=(4, 0))

    def build_reports(self):
        ttk.Label(self.reports_tab, text="Sales Reports", style="Header.TLabel").pack(anchor="w", pady=(0, 15))
        row = ttk.Frame(self.reports_tab)
        row.pack(anchor="w")
        ttk.Label(row, text="Report date (YYYY-MM-DD):").pack(side="left")
        self.report_date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(row, textvariable=self.report_date_var, width=18).pack(side="left", padx=8)
        ttk.Button(row, text="Generate Daily Report", command=self.generate_report).pack(side="left")
        self.report_text = tk.Text(self.reports_tab, height=22, wrap="word", font=("Consolas", 10))
        self.report_text.pack(fill="both", expand=True, pady=15)

    def refresh_all(self):
        self.refresh_dashboard()
        self.refresh_records()
        self.refresh_prices()

    def refresh_dashboard(self):
        data = self.api_call("GET", "/api/reports/summary", params={"date": date.today().isoformat()})
        if not data:
            return
        d = data["day"]
        self.card_values["customers"].config(text=str(d["customers"]))
        self.card_values["refills"].config(text=str(d["refills"]))
        self.card_values["kg"].config(text=f'{d["kg"]:,.2f} kg')
        self.card_values["sales"].config(text=f'₱{d["sales"]:,.2f}')
        status_text = ", ".join(f'{x["payment_status"]}: {x["customers"]} customer(s)' for x in data["by_payment_status"]) or "No records yet"
        self.dashboard_info.config(text=f'Date: {data["date"]}     |     Payment status: {status_text}')

    def refresh_records(self):
        data = self.api_call("GET", "/api/transactions", params={"search": self.search_var.get().strip(), "per_page": 100})
        if data is None:
            return
        for item in self.records_tree.get_children():
            self.records_tree.delete(item)
        if not data["transactions"] and self.search_var.get().strip().isdigit():
            messagebox.showinfo("Search Result", "Customer ID not found.")
        for r in data["transactions"]:
            self.records_tree.insert("", "end", iid=str(r["id"]), values=(
                r.get("customer_id", r["id"]), r["created_at"], r["customer_name"], r.get("payment_status", "Paid"), r["tank_count"],
                f'{r["total_kg"]:,.2f}', f'₱{r["total"]:,.2f}'))

    def clear_search(self):
        self.search_var.set("")
        self.refresh_records()

    def selected_record_id(self):
        selected = self.records_tree.selection()
        if not selected:
            messagebox.showwarning("Select record", "Please select a refill record first.")
            return None
        return int(selected[0])

    def on_select_record(self, _event):
        selected = self.records_tree.selection()
        self.selected_id = int(selected[0]) if selected else None

    def fetch_record(self, tid):
        return self.api_call("GET", f"/api/transactions/{tid}")

    def record_details(self, record):
        lines = [f'Customer ID: {record.get("customer_id", record["id"])}', f'Refill Transaction No.: {record["id"]}', f'Date: {record["created_at"]}',
                 f'Customer: {record["customer_name"]}', f'Payment Status: {record.get("payment_status", "Paid")}', "",
                 "TANK SIZE       QTY       PRICE EACH       SUBTOTAL"]
        for line in record["items"]:
            lines.append(f'{line["size_kg"]:>7g} kg       {line["quantity"]:>3}       '
                         f'₱{line["unit_price"]:>10,.2f}       ₱{line["subtotal"]:>10,.2f}')
        lines += ["", f'Total tanks: {record["tank_count"]}', f'Total KG: {record["total_kg"]:,.2f}',
                  f'TOTAL: ₱{record["total"]:,.2f}']
        return "\n".join(lines)

    def view_refill(self):
        tid = self.selected_record_id()
        if tid is None: return
        record = self.fetch_record(tid)
        if record:
            messagebox.showinfo("Refill Details", self.record_details(record))

    def transaction_form(self, title, record=None):
        price_data = self.api_call("GET", "/api/prices")
        if not price_data:
            return
        all_prices = price_data["prices"]
        tank_prices = all_prices
        if not tank_prices:
            messagebox.showerror("No tank prices", "Please add tank prices in Price Management.")
            return

        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("720x610")
        win.minsize(650, 520)
        win.transient(self.root)
        win.grab_set()
        form = ttk.Frame(win, padding=20)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=title, style="Header.TLabel").pack(anchor="w", pady=(0, 12))

        top = ttk.Frame(form)
        top.pack(fill="x", pady=(0, 12))
        ttk.Label(top, text="Customer name:").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        name_var = tk.StringVar(value=record["customer_name"] if record else "")
        ttk.Entry(top, textvariable=name_var, width=35).grid(row=0, column=1, sticky="w", pady=5)
        ttk.Label(top, text="Payment status:").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        status_var = tk.StringVar(value=record.get("payment_status", "Paid") if record else "Paid")
        ttk.Combobox(top, textvariable=status_var, values=("Paid", "Unpaid"), state="readonly", width=32).grid(row=1, column=1, sticky="w", pady=5)

        ttk.Separator(form).pack(fill="x", pady=8)
        ttk.Label(form, text="Tank sizes and quantities (add as many different sizes as needed)",
                  font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 8))
        line_header = ttk.Frame(form)
        line_header.pack(fill="x")
        ttk.Label(line_header, text="Tank size (KG)", width=22).pack(side="left")
        ttk.Label(line_header, text="Quantity", width=15).pack(side="left")
        rows_frame = ttk.Frame(form)
        rows_frame.pack(fill="x")
        line_rows = []

        # Tank size choices come from the current price list.
        size_options = sorted({p["size_kg"] for p in tank_prices} |
                              ({item["size_kg"] for item in record["items"]} if record else set()))
        def add_line(size=None, quantity="1"):
            row = ttk.Frame(rows_frame)
            row.pack(fill="x", pady=3)
            size_var = tk.StringVar(value=str(size if size is not None else (tank_prices[0]["size_kg"])))
            qty_var = tk.StringVar(value=str(quantity))
            size_box = ttk.Combobox(row, textvariable=size_var,
                                    values=[f"{x:g}" for x in size_options], state="readonly", width=19)
            size_box.pack(side="left", padx=(0, 12))
            # Allow free typing; validate quantity only when the user saves.
            qty_entry = ttk.Entry(row, textvariable=qty_var, width=13)
            qty_entry.pack(side="left", padx=(0, 12))
            remove_btn = ttk.Button(row, text="Remove", command=lambda: remove_line(row))
            remove_btn.pack(side="left")
            line_rows.append((row, size_var, qty_var))
            size_var.trace_add("write", lambda *_: calculate_total())
            qty_var.trace_add("write", lambda *_: calculate_total())
            calculate_total()

        def remove_line(row):
            if len(line_rows) <= 1:
                messagebox.showwarning("Required tank", "At least one tank size is required.", parent=win)
                return
            for item in list(line_rows):
                if item[0] == row:
                    line_rows.remove(item)
                    break
            row.destroy()
            calculate_total()

        ttk.Button(form, text="+ Add Another Tank Size", command=lambda: add_line()).pack(anchor="w", pady=8)
        summary = ttk.Label(form, text="", font=("Segoe UI", 11, "bold"), foreground="#12345a")
        summary.pack(anchor="w", pady=12)

        def calculate_total():
            total = 0.0
            kg_total = 0.0
            tank_total = 0
            try:
                for _, size_var, qty_var in line_rows:
                    size = float(size_var.get())
                    qty = int(qty_var.get())
                    if qty < 1:
                        raise ValueError
                    price_row = next((p for p in all_prices if float(p["size_kg"]) == size), None)
                    if not price_row:
                        raise ValueError
                    total += float(price_row["price"]) * qty
                    kg_total += size * qty
                    tank_total += qty
                summary.config(text=f"Total tanks: {tank_total}    |    Total KG: {kg_total:g}    |    Estimated total: ₱{total:,.2f}")
            except (ValueError, StopIteration):
                summary.config(text="Enter valid tank sizes and whole-number quantities greater than 0.")

        if record:
            for item in record["items"]:
                add_line(item["size_kg"], item["quantity"])
        else:
            add_line()

        original_state = None
        if record:
            original_state = (record["customer_name"], record.get("payment_status", "Paid"),
                              sorted((round(float(i["size_kg"]), 2), int(i["quantity"])) for i in record["items"]))

        def save():
            customer = name_var.get().strip()
            if not customer or not all(ch.isalpha() or ch.isspace() for ch in customer):
                messagebox.showwarning("Validation", "Customer name must contain letters and spaces only.", parent=win)
                return
            items = []
            try:
                for _, size_var, qty_var in line_rows:
                    size = float(size_var.get())
                    qty = int(qty_var.get())
                    if qty < 1:
                        raise ValueError
                    items.append({"size_kg": size, "quantity": qty})
                if not items:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Validation", "Every tank line needs a valid tank size and a whole-number quantity greater than 0.", parent=win)
                return
            body = {"customer_name": customer, "payment_status": status_var.get(), "items": items}
            if record:
                proposed_state = (customer, status_var.get(), sorted((round(float(i["size_kg"]), 2), int(i["quantity"])) for i in items))
                if proposed_state == original_state:
                    messagebox.showwarning("Validation", "No changes detected. Please update at least one field.", parent=win)
                    return
                result = self.api_call("PUT", f'/api/transactions/{record["id"]}', body)
            else:
                result = self.api_call("POST", "/api/transactions", body)
            if result:
                messagebox.showinfo("Saved", "Customer refill record saved successfully.", parent=win)
                win.destroy()
                self.refresh_all()

        footer = ttk.Frame(form)
        footer.pack(side="bottom", fill="x", pady=(15, 0))
        ttk.Button(footer, text="Save Customer Refill", command=save).pack(side="right", padx=5)
        def cancel_form():
            if record:
                if messagebox.askyesno("Confirm Cancel", "Discard your changes?", parent=win):
                    win.destroy()
            else:
                if messagebox.askyesno("Confirm Cancel", "Discard this refill entry?", parent=win):
                    win.destroy()
        ttk.Button(footer, text="Cancel", command=cancel_form).pack(side="right", padx=5)

    def add_refill(self):
        self.transaction_form("Add New Refill")

    def update_refill(self):
        tid=self.selected_record_id()
        if tid is None: return
        record=self.fetch_record(tid)
        if record: self.transaction_form("Update Refill Record",record)

    def delete_refill(self):
        tid=self.selected_record_id()
        if tid is None: return
        record=self.fetch_record(tid)
        if not record: return
        if not messagebox.askyesno("Confirm Delete",f'{self.record_details(record)}\n\nPermanently delete this refill?'):
            return
        try:
            status, payload = self.api.request("DELETE", f"/api/transactions/{tid}")
            if status == 204:
                messagebox.showinfo("Deleted", "Refill record deleted.")
                self.refresh_all()
            else:
                messagebox.showerror("Delete failed", payload.get("error", "Could not delete the record."))
        except ConnectionError as exc:
            messagebox.showerror("API connection", str(exc))

    def refresh_prices(self):
        data=self.api_call("GET","/api/prices")
        if not data: return
        self.prices=data["prices"]
        for item in self.price_tree.get_children(): self.price_tree.delete(item)
        for p in self.prices:
            self.price_tree.insert("","end",iid=str(p["size_kg"]),values=(
                f'{p["size_kg"]:g} kg',f'₱{p["price"]:,.2f}',p["updated_at"]))

    def update_price(self):
        selected=self.price_tree.selection()
        if not selected:
            messagebox.showwarning("Select price","Select a tank size first."); return
        try:
            price=float(self.new_price_var.get())
            if not 0<price<=100000: raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid price","Enter a number greater than 0 and not above 100,000."); return
        size=float(selected[0])
        result=self.api_call("PUT",f"/api/prices/{size:g}",{"price":price})
        if result:
            messagebox.showinfo("Price updated",f'{size:g} kg price updated to ₱{price:,.2f}.')
            self.new_price_var.set("")
            self.refresh_prices()

    def generate_report(self):
        day=self.report_date_var.get().strip()
        data=self.api_call("GET","/api/reports/summary",params={"date":day})
        if not data: return
        d=data["day"]
        lines=[f"EL-GAS REFILLING STATION - DAILY SALES REPORT",f"Date: {data['date']}",
               "-"*58,f"Total customers: {d['customers']}",f"Total refills: {d['refills']}",
               f"Total kilograms: {d['kg']:,.2f} kg",f"Total sales: ₱{d['sales']:,.2f}","",
               "PAYMENT STATUS SUMMARY","-"*58]
        for row in data["by_payment_status"]:
            lines.append(f'{row["payment_status"]:<12} {row["customers"]:>4} customer(s)    ₱{row["amount"]:>12,.2f}')
        if not data["by_payment_status"]: lines.append("No transactions for this date.")
        self.report_text.delete("1.0","end")
        self.report_text.insert("1.0","\n".join(lines))


if __name__ == "__main__":
    root=tk.Tk()
    app=ElgasGUI(root)
    root.mainloop()
