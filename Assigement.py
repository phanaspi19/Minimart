#Tola
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import mysql.connector
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
import qrcode

# --- Use ttkbootstrap for a modern, cute UI ---
try:
    import ttkbootstrap as tb
    from ttkbootstrap.constants import *
    THEME_AVAILABLE = True
except ImportError:
    THEME_AVAILABLE = False

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "port": 3306,  
    "password": "123456",
    "database": "minimart",
}


class DatabaseManager:
    def __init__(self, db_config=None):
        self.db_config = db_config or DB_CONFIG
        self.conn = None
        self.cursor = None
        self.connect()
        self.create_tables()

    def connect(self):
        try:
            self.conn = mysql.connector.connect(
                host=self.db_config["host"],
                port=self.db_config["port"],
                user=self.db_config["user"],
                password=self.db_config["password"],
                database=self.db_config["database"],
            )
            self.cursor = self.conn.cursor()
            print("Connected to MySQL database successfully.")
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Failed to connect to MySQL database: {e}")

    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL UNIQUE,
                category VARCHAR(255),
                import_price DECIMAL(10, 2) NOT NULL,
                selling_price DECIMAL(10, 2) NOT NULL,
                quantity INT NOT NULL,
                supplier VARCHAR(255),
                date_added DATE
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sales (
                id INT AUTO_INCREMENT PRIMARY KEY,
                product_id INT,
                product_name VARCHAR(255) NOT NULL,
                quantity INT NOT NULL,
                unit_price DECIMAL(10, 2) NOT NULL,
                total_price DECIMAL(10, 2) NOT NULL,
                sale_date DATETIME,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        ''')

        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INT AUTO_INCREMENT PRIMARY KEY,
                description VARCHAR(255) NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                expense_date DATETIME
            )
        ''')
        self.conn.commit()
        print("Tables checked/created.")

    def add_product(self, name, category, import_price, selling_price, quantity, supplier):
        try:
            # Convert prices to Decimal before storing
            import_price_dec = Decimal(import_price)
            selling_price_dec = Decimal(selling_price)

            date_added = datetime.now().strftime("%Y-%m-%d")
            self.cursor.execute(
                "INSERT INTO products (name, category, import_price, selling_price, quantity, supplier, date_added) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (name, category, import_price_dec, selling_price_dec, quantity, supplier, date_added)
            )
            self.conn.commit()
            return self.cursor.lastrowid
        except mysql.connector.IntegrityError:
            messagebox.showerror("Database Error", "Product with this name already exists.")
            return False
        except mysql.connector.Error as e:
            messagebox.showerror("Database Error", f"Error adding product: {e}")
            return False
        except InvalidOperation:
            messagebox.showerror("Input Error", "Import Price or Selling Price is not a valid number.")
            return False
        except Exception as e:
            messagebox.showerror("Database Error", f"Error adding product: {e}")
            return False

    def get_products(self, search_query=""):
        if search_query:
            self.cursor.execute(
                "SELECT * FROM products WHERE name LIKE %s OR category LIKE %s OR supplier LIKE %s",
                (f"%{search_query}%", f"%{search_query}%", f"%{search_query}%")
            )
        else:
            self.cursor.execute("SELECT * FROM products")
        return self.cursor.fetchall()

    def update_product(self, id, name, category, import_price, selling_price, quantity, supplier):
        try:
            # Convert prices to Decimal before storing
            import_price_dec = Decimal(import_price)
            selling_price_dec = Decimal(selling_price)

            self.cursor.execute(
                "UPDATE products SET name=%s, category=%s, import_price=%s, selling_price=%s, quantity=%s, supplier=%s WHERE id=%s",
                (name, category, import_price_dec, selling_price_dec, quantity, supplier, id)
            )
            self.conn.commit()
            return True
        except InvalidOperation:
            messagebox.showerror("Input Error", "Import Price or Selling Price is not a valid number.")
            return False
        except Exception as e:
            messagebox.showerror("Database Error", f"Error updating product: {e}")
            return False

    def delete_product(self, id):
        try:
            self.cursor.execute("DELETE FROM products WHERE id=%s", (id,))
            self.conn.commit()
            return True
        except Exception as e:
            messagebox.showerror("Database Error", f"Error deleting product: {e}")
            return False

    def update_product_quantity(self, product_id, new_quantity):
        try:
            self.cursor.execute("UPDATE products SET quantity = %s WHERE id = %s", (new_quantity, product_id))
            self.conn.commit()
            return True
        except Exception as e:
            messagebox.showerror("Database Error", f"Error updating product quantity: {e}")
            return False

    def record_sale(self, cart_items):
        try:
            for item in cart_items:
                prod_id, prod_name, qty, unit_price, total_price = item
                sale_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Ensure unit_price and total_price are Decimal when inserting
                self.cursor.execute(
                    "INSERT INTO sales (product_id, product_name, quantity, unit_price, total_price, sale_date) VALUES (%s, %s, %s, %s, %s, %s)",
                    (prod_id, prod_name, qty, unit_price, total_price, sale_date)
                )

                self.cursor.execute("SELECT quantity FROM products WHERE id = %s", (prod_id,))
                current_qty = self.cursor.fetchone()[0]
                new_qty = current_qty - qty
                self.update_product_quantity(prod_id, new_qty)

            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback() # Rollback if any error occurs
            messagebox.showerror("Sale Error", f"Failed to record sale: {e}")
            return False

    def get_sales_history(self):
        self.cursor.execute("SELECT * FROM sales ORDER BY sale_date DESC")
        return self.cursor.fetchall()

    def get_sales_sum_by_period(self, period, date_value_str): # Renamed date_value to date_value_str for clarity
        total_sales = Decimal('0.00')
        query = ""
        params = ()

        try:
            if period != "all":
                # Convert the date string to a datetime object FIRST
                # Assuming 'YYYY-MM-DD' format for date_value_str from UI
                date_value_dt = datetime.strptime(date_value_str, '%Y-%m-%d')

            if period == "day":
                query = "SELECT SUM(total_price) FROM sales WHERE DATE(sale_date) = %s"
                params = (date_value_dt.strftime('%Y-%m-%d'),)
            elif period == "week":
                # Get the start of the week (Monday = 0)
                start_of_week = date_value_dt - timedelta(days=date_value_dt.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                query = "SELECT SUM(total_price) FROM sales WHERE DATE(sale_date) BETWEEN %s AND %s"
                params = (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d'))
            elif period == "month":
                query = "SELECT SUM(total_price) FROM sales WHERE DATE_FORMAT(sale_date, '%Y-%m') = %s"
                params = (date_value_dt.strftime('%Y-%m'),)
            elif period == "year":
                query = "SELECT SUM(total_price) FROM sales WHERE DATE_FORMAT(sale_date, '%Y') = %s"
                params = (date_value_dt.strftime('%Y'),)
            else: # All time
                query = "SELECT SUM(total_price) FROM sales"
                params = ()

            self.cursor.execute(query, params)
            result = self.cursor.fetchone()[0]
            if result:
                total_sales = Decimal(result)
        except ValueError:
            # This should ideally be caught by the UI before calling this function
            print(f"DEBUG: Invalid date format passed to get_sales_sum_by_period: {date_value_str}")
        except Exception as e:
            messagebox.showerror("Database Error", f"Error getting sales sum: {e}")
        return total_sales

    def add_expense(self, description, amount):
        try:
            expense_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # Convert amount to Decimal before storing
            amount_dec = Decimal(amount)
            self.cursor.execute(
                "INSERT INTO expenses (description, amount, expense_date) VALUES (%s, %s, %s)",
                (description, amount_dec, expense_date)
            )
            self.conn.commit()
            return True
        except InvalidOperation:
            messagebox.showerror("Input Error", "Expense amount is not a valid number.")
            return False
        except Exception as e:
            messagebox.showerror("Database Error", f"Error adding expense: {e}")
            return False

    def get_expenses_by_period(self, period, date_value_str):
        query = ""
        params = ()

        try:
            if period != "all":
                date_value_dt = datetime.strptime(date_value_str, '%Y-%m-%d')

            if period == "day":
                query = "SELECT * FROM expenses WHERE DATE(expense_date) = %s ORDER BY expense_date DESC"
                params = (date_value_dt.strftime('%Y-%m-%d'),)
            elif period == "week":
                start_of_week = date_value_dt - timedelta(days=date_value_dt.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                query = "SELECT * FROM expenses WHERE DATE(expense_date) BETWEEN %s AND %s ORDER BY expense_date DESC"
                params = (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d'))
            elif period == "month":
                query = "SELECT * FROM expenses WHERE DATE_FORMAT(expense_date, '%Y-%m') = %s ORDER BY expense_date DESC"
                params = (date_value_dt.strftime('%Y-%m'),)
            elif period == "year":
                query = "SELECT * FROM expenses WHERE DATE_FORMAT(expense_date, '%Y') = %s ORDER BY expense_date DESC"
                params = (date_value_dt.strftime('%Y'),)
            else: # All time
                query = "SELECT * FROM expenses ORDER BY expense_date DESC"
                params = ()

            self.cursor.execute(query, params)
            return self.cursor.fetchall()
        except ValueError:
            print(f"DEBUG: Invalid date format passed to get_expenses_by_period: {date_value_str}")
            return []
        except Exception as e:
            messagebox.showerror("Database Error", f"Error getting expenses history: {e}")
            return []
    #phea
    def get_expenses_sum_by_period(self, period, date_value_str):
        total_expenses = Decimal('0.00')
        query = ""
        params = ()

        try:
            if period != "all":
                date_value_dt = datetime.strptime(date_value_str, '%Y-%m-%d')

            if period == "day":
                query = "SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) = %s"
                params = (date_value_dt.strftime('%Y-%m-%d'),)
            elif period == "week":
                start_of_week = date_value_dt - timedelta(days=date_value_dt.weekday())
                end_of_week = start_of_week + timedelta(days=6)
                query = "SELECT SUM(amount) FROM expenses WHERE DATE(expense_date) BETWEEN %s AND %s"
                params = (start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d'))
            elif period == "month":
                query = "SELECT SUM(amount) FROM expenses WHERE DATE_FORMAT(expense_date, '%Y-%m') = %s"
                params = (date_value_dt.strftime('%Y-%m'),)
            elif period == "year":
                query = "SELECT SUM(amount) FROM expenses WHERE DATE_FORMAT(expense_date, '%Y') = %s"
                params = (date_value_dt.strftime('%Y'),)
            else: # All time
                query = "SELECT SUM(amount) FROM expenses"
                params = ()

            self.cursor.execute(query, params)
            result = self.cursor.fetchone()[0]
            if result:
                total_expenses = Decimal(result)
        except ValueError:
            print(f"DEBUG: Invalid date format passed to get_expenses_sum_by_period: {date_value_str}")
        except Exception as e:
            messagebox.showerror("Database Error", f"Error getting expenses sum: {e}")
        return total_expenses

    def close(self):
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

   
class MiniMartApp:
    def __init__(self, root):
        if THEME_AVAILABLE:
            # Use a cute theme from ttkbootstrap
            self.style = tb.Style("minty")
            self.root = self.style.master
        else:
            self.root = root
        self.root.title("Mini Mart System 🛒✨")
        self.root.geometry("1200x700")
        # Add a cute icon if you have one (optional)
        # self.root.iconbitmap('cute_icon.ico')

        # Add a cute title label
        title_font = ("Comic Sans MS", 28, "bold") if THEME_AVAILABLE else ("Arial", 24, "bold")
        title_fg = "#6c63ff" if THEME_AVAILABLE else "#4CAF50"
        title_bg = self.root.cget("background")
        self.label_title = tk.Label(self.root, text="Welcome to Mini Mart! 🐻🍭", font=title_font, fg=title_fg, bg=title_bg)
        self.label_title.pack(pady=10)

        self.db = DatabaseManager()
        self.cart = [] # (product_id, name, quantity, unit_price, total_price)
        self.product_data_map = {} # Maps product ID to dict of product info
        self.qr_storage_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_codes")
        self.ensure_qr_folder()

        self.create_widgets()
        self.load_products()
        self.load_sales_history()
        self.update_income_expenses()

                              
    def create_widgets(self):
        if THEME_AVAILABLE:
            self.notebook = tb.Notebook(self.root, bootstyle="info")
        else:
            self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(pady=10, expand=True, fill="both")
        # Add a cute emoji tab bar
        self.products_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.products_frame, text="🛍️ Products")
        self.cart_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cart_frame, text="🛒 Cart & Checkout")
        self.income_expenses_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.income_expenses_frame, text="💸 Income & Expenses")
        self.sales_history_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.sales_history_frame, text="📈 Sales History")
        self.create_products_tab(self.products_frame)
        self.create_cart_tab(self.cart_frame)
        self.create_income_expenses_tab(self.income_expenses_frame)
        self.create_sales_history_tab(self.sales_history_frame)

    def create_products_tab(self, parent_frame):
        # Set cute background for ttk.Frame using style
        style = ttk.Style()
        style.configure("Cute.TFrame", background="#f7e6ff")
        style.configure("Cute.TLabelframe", background="#f7e6ff", borderwidth=2, relief="ridge")
        style.configure("Cute.TLabelframe.Label", background="#f7e6ff", font=("Comic Sans MS", 16, "bold"), foreground="#b266ff")
        # Button style for large, playful font
        if THEME_AVAILABLE:
            style.configure("Cute.TButton", font=("Comic Sans MS", 14, "bold"), padding=8)
        else:
            style.configure("Large.TButton", font=("Comic Sans MS", 14, "bold"), padding=8)
        parent_frame.configure(style="Cute.TFrame")
        # Search Products
        search_frame = ttk.LabelFrame(parent_frame, text="🔎 Search Products", style="Cute.TLabelframe")
        search_frame.pack(padx=14, pady=8, fill="x")

        label_font = ("Comic Sans MS", 14)
        entry_font = ("Comic Sans MS", 14)
        tree_font = ("Comic Sans MS", 13)

        ttk.Label(search_frame, text="Search Product:", font=label_font).grid(row=0, column=0, padx=7, pady=7, sticky="w")
        self.entry_search_product = ttk.Entry(search_frame, width=40, font=entry_font)
        self.entry_search_product.grid(row=0, column=1, padx=7, pady=7, sticky="ew")
        if THEME_AVAILABLE:
            tb.Button(search_frame, text="Search", command=self.search_products, bootstyle="info-outline", width=10, style="Cute.TButton").grid(row=0, column=2, padx=5, pady=5)
            tb.Button(search_frame, text="Clear Search", command=self.clear_search, bootstyle="secondary-outline", width=12, style="Cute.TButton").grid(row=0, column=3, padx=5, pady=5)
        else:
            ttk.Button(search_frame, text="Search", command=self.search_products, style="Large.TButton").grid(row=0, column=2, padx=5, pady=5)
            ttk.Button(search_frame, text="Clear Search", command=self.clear_search, style="Large.TButton").grid(row=0, column=3, padx=5, pady=5)

        search_frame.grid_columnconfigure(1, weight=1)

        # Product Details Input
        details_frame = ttk.LabelFrame(parent_frame, text="🧸 Product Details", style="Cute.TLabelframe")
        details_frame.pack(padx=14, pady=8, fill="x")

        ttk.Label(details_frame, text="Name:", font=label_font).grid(row=0, column=0, padx=7, pady=7, sticky="w")
        self.entry_name = ttk.Entry(details_frame, width=30, font=entry_font)
        self.entry_name.grid(row=0, column=1, padx=7, pady=7, sticky="ew")

        ttk.Label(details_frame, text="Category:", font=label_font).grid(row=0, column=2, padx=7, pady=7, sticky="w")
        self.entry_category = ttk.Entry(details_frame, width=20, font=entry_font)
        self.entry_category.grid(row=0, column=3, padx=7, pady=7, sticky="ew")

        ttk.Label(details_frame, text="Import Price:", font=label_font).grid(row=0, column=4, padx=7, pady=7, sticky="w")
        self.entry_import_price = ttk.Entry(details_frame, width=15, font=entry_font)
        self.entry_import_price.grid(row=0, column=5, padx=7, pady=7, sticky="ew")

        ttk.Label(details_frame, text="Selling Price:", font=label_font).grid(row=1, column=0, padx=7, pady=7, sticky="w")
        self.entry_selling_price = ttk.Entry(details_frame, width=30, font=entry_font)
        self.entry_selling_price.grid(row=1, column=1, padx=7, pady=7, sticky="ew")

        ttk.Label(details_frame, text="Quantity:", font=label_font).grid(row=1, column=2, padx=7, pady=7, sticky="w")
        self.entry_quantity = ttk.Entry(details_frame, width=20, font=entry_font)
        self.entry_quantity.grid(row=1, column=3, padx=7, pady=7, sticky="ew")

        ttk.Label(details_frame, text="Supplier:", font=label_font).grid(row=1, column=4, padx=7, pady=7, sticky="w")
        self.entry_supplier = ttk.Entry(details_frame, width=15, font=entry_font)
        self.entry_supplier.grid(row=1, column=5, padx=7, pady=7, sticky="ew")

        # Configure columns to expand
        for i in range(6):
            details_frame.grid_columnconfigure(i, weight=1)

        # Product Actions Buttons
        button_frame = ttk.Frame(parent_frame)
        button_frame.pack(padx=10, pady=8, fill="x")
        if THEME_AVAILABLE:
            btn_style = {"style": "Cute.TButton"}
        else:
            btn_style = {"style": "Large.TButton"}
        tb.Button(button_frame, text="Add Product 🧃", command=self.add_product, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(button_frame, text="Add Product 🧃", command=self.add_product, **btn_style).pack(side="left", padx=7)
        tb.Button(button_frame, text="Update Product ✏️", command=self.update_product, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(button_frame, text="Update Product ✏️", command=self.update_product, **btn_style).pack(side="left", padx=7)
        tb.Button(button_frame, text="Generate QR 📷", command=self.generate_selected_product_qr, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(button_frame, text="Generate QR 📷", command=self.generate_selected_product_qr, **btn_style).pack(side="left", padx=7)
        tb.Button(button_frame, text="Delete Product 🗑️", command=self.delete_product, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(button_frame, text="Delete Product 🗑️", command=self.delete_product, **btn_style).pack(side="left", padx=7)
        tb.Button(button_frame, text="Clear Fields 🧹", command=self.clear_product_fields, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(button_frame, text="Clear Fields 🧹", command=self.clear_product_fields, **btn_style).pack(side="left", padx=7)

        # Products Treeview
        self.tree_products = ttk.Treeview(parent_frame, columns=("ID", "Name", "Category", "Import Price", "Selling Price", "Quantity", "Supplier", "Date Added"), show="headings")
        self.tree_products.pack(padx=10, pady=5, expand=True, fill="both")
        self.tree_products.tag_configure('largefont', font=tree_font)

        # Define column headings
        self.tree_products.heading("ID", text="ID")
        self.tree_products.heading("Name", text="Name")
        self.tree_products.heading("Category", text="Category")
        self.tree_products.heading("Import Price", text="Import Price")
        self.tree_products.heading("Selling Price", text="Selling Price")
        self.tree_products.heading("Quantity", text="Quantity")
        self.tree_products.heading("Supplier", text="Supplier")
        self.tree_products.heading("Date Added", text="Date Added")

        # Set column widths (adjust as needed)
        self.tree_products.column("ID", width=30, anchor="center")
        self.tree_products.column("Name", width=150)
        self.tree_products.column("Category", width=100)
        self.tree_products.column("Import Price", width=100, anchor="e")
        self.tree_products.column("Selling Price", width=100, anchor="e")
        self.tree_products.column("Quantity", width=70, anchor="center")
        self.tree_products.column("Supplier", width=100)
        self.tree_products.column("Date Added", width=100, anchor="center")

        self.tree_products.bind("<<TreeviewSelect>>", self.on_product_select)

    def create_cart_tab(self, parent_frame):
        label_font = ("Comic Sans MS", 14)
        entry_font = ("Comic Sans MS", 14)
        tree_font = ("Comic Sans MS", 13)
        # Product Selection and Quantity for Cart
        cart_input_frame = ttk.LabelFrame(parent_frame, text="🦄 Add to Cart (So Cute!) 🦄", style="Cute.TLabelframe")
        cart_input_frame.pack(padx=14, pady=8, fill="x")

        ttk.Label(cart_input_frame, text="Select Product 🧸:", font=label_font).grid(row=0, column=0, padx=7, pady=7, sticky="w")
        self.combo_product = ttk.Combobox(cart_input_frame, state="readonly", width=50, font=entry_font)
        self.combo_product.grid(row=0, column=1, padx=7, pady=7, sticky="ew")
        self.combo_product.bind("<<ComboboxSelected>>", self.on_product_select_in_cart)

        ttk.Label(cart_input_frame, text="Quantity 🍬:", font=label_font).grid(row=0, column=2, padx=7, pady=7, sticky="w")
        self.entry_qty = ttk.Entry(cart_input_frame, width=10, font=entry_font)
        self.entry_qty.grid(row=0, column=3, padx=7, pady=7, sticky="ew")
        self.entry_qty.insert(0, "1") # Default quantity

        self.label_available_stock = ttk.Label(cart_input_frame, text="Available Stock: -", font=("Comic Sans MS", 12, "italic"))
        self.label_available_stock.grid(row=1, column=0, columnspan=2, padx=7, pady=2, sticky="w")
        self.label_selected_price = ttk.Label(cart_input_frame, text="Price: -", font=("Comic Sans MS", 12, "italic"))
        self.label_selected_price.grid(row=1, column=2, columnspan=2, padx=7, pady=2, sticky="w")

        if THEME_AVAILABLE:
            btn_style = {"style": "Cute.TButton"}
        else:
            btn_style = {"style": "Large.TButton"}
        tb.Button(cart_input_frame, text="Add to Cart 🦄", command=self.add_to_cart, **btn_style).grid(row=0, column=4, padx=7, pady=7) if THEME_AVAILABLE else ttk.Button(cart_input_frame, text="Add to Cart 🦄", command=self.add_to_cart, **btn_style).grid(row=0, column=4, padx=7, pady=7)

        cart_input_frame.grid_columnconfigure(1, weight=1)

        # Cart Treeview
        self.tree_cart = ttk.Treeview(parent_frame, columns=("ID", "Name", "Quantity", "Unit Price", "Total Price"), show="headings")
        self.tree_cart.pack(padx=14, pady=8, expand=True, fill="both")
        self.tree_cart.tag_configure('largefont', font=tree_font)

        self.tree_cart.heading("ID", text="ID 🧸")
        self.tree_cart.heading("Name", text="Name 🥤")
        self.tree_cart.heading("Quantity", text="Qty 🍬")
        self.tree_cart.heading("Unit Price", text="Unit Price 💰")
        self.tree_cart.heading("Total Price", text="Total Price 💵")

        self.tree_cart.column("ID", width=50, anchor="center")
        self.tree_cart.column("Name", width=200)
        self.tree_cart.column("Quantity", width=80, anchor="center")
        self.tree_cart.column("Unit Price", width=100, anchor="e")
        self.tree_cart.column("Total Price", width=120, anchor="e")

        self.tree_cart.bind("<<TreeviewSelect>>", self.on_cart_item_select)

        # Cart Actions and Total
        cart_action_frame = ttk.Frame(parent_frame)
        cart_action_frame.pack(padx=10, pady=8, fill="x")

        if THEME_AVAILABLE:
            btn_style = {"style": "Cute.TButton"}
        else:
            btn_style = {"style": "Large.TButton"}
        tb.Button(cart_action_frame, text="Remove Selected 🗑️", command=self.remove_from_cart, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(cart_action_frame, text="Remove Selected 🗑️", command=self.remove_from_cart, **btn_style).pack(side="left", padx=7)
        tb.Button(cart_action_frame, text="Clear Cart 🧹", command=self.clear_cart, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(cart_action_frame, text="Clear Cart 🧹", command=self.clear_cart, **btn_style).pack(side="left", padx=7)
        tb.Button(cart_action_frame, text="Update Qty ✏️", command=self.update_cart_item_quantity, **btn_style).pack(side="left", padx=7) if THEME_AVAILABLE else ttk.Button(cart_action_frame, text="Update Qty ✏️", command=self.update_cart_item_quantity, **btn_style).pack(side="left", padx=7)

        self.label_cart_total = ttk.Label(cart_action_frame, text="Cart Total: 0.00 🦄", font=("Comic Sans MS", 18, "bold"))
        self.label_cart_total.pack(side="right", padx=14)

        checkout_frame = ttk.Frame(parent_frame)
        checkout_frame.pack(padx=10, pady=8, fill="x", anchor="e")
        if THEME_AVAILABLE:
            tb.Button(checkout_frame, text="Checkout 🦄", command=self.checkout, bootstyle="success", width=18, style="Cute.TButton").pack(side="right")
        else:
            ttk.Button(checkout_frame, text="Checkout 🦄", command=self.checkout, style="Accent.TButton").pack(side="right")
        s = ttk.Style()
        s.configure("Accent.TButton", background="#4CAF50", foreground="white", font=("Comic Sans MS", 16, "bold"))
        s.map("Accent.TButton", background=[('active', '#45a049')])

    #Phana
    def create_income_expenses_tab(self, parent_frame):
        label_font = ("Comic Sans MS", 14)
        entry_font = ("Comic Sans MS", 14)
        tree_font = ("Comic Sans MS", 13)
        # Expenses Input
        expense_frame = ttk.LabelFrame(parent_frame, text="Add Expense", style="Cute.TLabelframe")
        expense_frame.pack(padx=10, pady=5, fill="x")

        ttk.Label(expense_frame, text="Description:", font=label_font).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_expense_desc = ttk.Entry(expense_frame, width=40, font=entry_font)
        self.entry_expense_desc.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(expense_frame, text="Amount:", font=label_font).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.entry_expense_amount = ttk.Entry(expense_frame, width=15, font=entry_font)
        self.entry_expense_amount.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        if THEME_AVAILABLE:
            tb.Button(expense_frame, text="Add Expense", command=self.add_expense, bootstyle="danger-outline", width=14, style="Cute.TButton").grid(row=0, column=4, padx=5, pady=5)
        else:
            ttk.Button(expense_frame, text="Add Expense", command=self.add_expense, style="Large.TButton").grid(row=0, column=4, padx=5, pady=5)

        expense_frame.grid_columnconfigure(1, weight=1)

        # Summary Display
        summary_frame = ttk.LabelFrame(parent_frame, text="Summary", style="Cute.TLabelframe")
        summary_frame.pack(padx=10, pady=10, fill="x")

        # Period selection for summary
        ttk.Label(summary_frame, text="View Period:", font=label_font).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.period_var = tk.StringVar(value="day") # Default to 'day'
        self.period_combobox = ttk.Combobox(summary_frame, textvariable=self.period_var,
                                            values=["day", "week", "month", "year", "all"], state="readonly", font=entry_font)
        self.period_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.period_combobox.bind("<<ComboboxSelected>>", self.update_income_expenses)

        ttk.Label(summary_frame, text="Date (YYYY-MM-DD):", font=label_font).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.date_entry = ttk.Entry(summary_frame, width=15, font=entry_font)
        self.date_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d')) # Default to today
        self.date_entry.bind("<Return>", self.update_income_expenses) # Update on Enter key

        if THEME_AVAILABLE:
            tb.Button(summary_frame, text="Refresh", command=self.update_income_expenses, bootstyle="info-outline", width=10, style="Cute.TButton").grid(row=0, column=4, padx=5, pady=5)
        else:
            ttk.Button(summary_frame, text="Refresh", command=self.update_income_expenses, style="Large.TButton").grid(row=0, column=4, padx=5, pady=5)

        self.label_total_income = ttk.Label(summary_frame, text="Total Income: 0.00", font=("Comic Sans MS", 16, "bold"))
        self.label_total_income.grid(row=1, column=0, columnspan=5, pady=5, sticky="w")

        self.label_total_expenses = ttk.Label(summary_frame, text="Total Expenses: 0.00", font=("Comic Sans MS", 16, "bold"))
        self.label_total_expenses.grid(row=2, column=0, columnspan=5, pady=5, sticky="w")

        self.label_net_profit = ttk.Label(summary_frame, text="Net Profit: 0.00", font=("Comic Sans MS", 20, "bold"))
        self.label_net_profit.grid(row=3, column=0, columnspan=5, pady=10, sticky="w")
        
        # Expenses History Treeview (added for completeness)
        self.expense_history_frame = ttk.LabelFrame(parent_frame, text="Expense History", style="Cute.TLabelframe")
        self.expense_history_frame.pack(padx=10, pady=5, fill="both", expand=True)

        self.tree_expense_history = ttk.Treeview(self.expense_history_frame, columns=("ID", "Description", "Amount", "Date"), show="headings")
        self.tree_expense_history.pack(padx=5, pady=5, fill="both", expand=True)
        self.tree_expense_history.tag_configure('largefont', font=tree_font)

        self.tree_expense_history.heading("ID", text="ID")
        self.tree_expense_history.heading("Description", text="Description")
        self.tree_expense_history.heading("Amount", text="Amount")
        self.tree_expense_history.heading("Date", text="Date")

        self.tree_expense_history.column("ID", width=50, anchor="center")
        self.tree_expense_history.column("Description", width=200)
        self.tree_expense_history.column("Amount", width=100, anchor="e")
        self.tree_expense_history.column("Date", width=150, anchor="center")

                                            
                                          
    def create_sales_history_tab(self, parent_frame):
        tree_font = ("Comic Sans MS", 13)
        # Sales History Treeview
        self.tree_sales_history = ttk.Treeview(parent_frame, columns=("ID", "Product Name", "Quantity", "Unit Price", "Total Price", "Sale Date"), show="headings")
        self.tree_sales_history.pack(padx=10, pady=10, expand=True, fill="both")
        self.tree_sales_history.tag_configure('largefont', font=tree_font)

        self.tree_sales_history.heading("ID", text="Sale ID")
        self.tree_sales_history.heading("Product Name", text="Product Name")
        self.tree_sales_history.heading("Quantity", text="Quantity")
        self.tree_sales_history.heading("Unit Price", text="Unit Price")
        self.tree_sales_history.heading("Total Price", text="Total Price")
        self.tree_sales_history.heading("Sale Date", text="Sale Date")

        self.tree_sales_history.column("ID", width=50, anchor="center")
        self.tree_sales_history.column("Product Name", width=200)
        self.tree_sales_history.column("Quantity", width=80, anchor="center")
        self.tree_sales_history.column("Unit Price", width=100, anchor="e")
        self.tree_sales_history.column("Total Price", width=120, anchor="e")
        self.tree_sales_history.column("Sale Date", width=150, anchor="center")

    # --- Product Management Functions ---
    def ensure_qr_folder(self):
        os.makedirs(self.qr_storage_folder, exist_ok=True)

    def slugify(self, value):
        value = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
        return value.strip("_") or "product"

    def generate_product_qr_code(self, product_id, name, category="", selling_price=""):
        try:
            self.ensure_qr_folder()
            safe_name = self.slugify(name)
            file_name = f"product_{product_id}_{safe_name}.png"
            file_path = os.path.join(self.qr_storage_folder, file_name)
            payload = f"Product ID: {product_id}\nName: {name}\nCategory: {category}\nPrice: {selling_price}"

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(payload)
            qr.make(fit=True)
            image = qr.make_image(fill_color="#1f4e79", back_color="white")
            image.save(file_path)
            return file_path
        except Exception as e:
            messagebox.showerror("QR Error", f"Failed to create QR code: {e}")
            return None

    def generate_selected_product_qr(self):
        selected_item = self.tree_products.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a product first.")
            return

        values = self.tree_products.item(selected_item)['values']
        product_id = values[0]
        name = values[1]
        category = values[2]
        selling_price = values[4]

        file_path = self.generate_product_qr_code(product_id, name, category, selling_price)
        if file_path:
            messagebox.showinfo("QR Code Saved", f"QR code saved to:\n{file_path}")

    def load_products(self, search_query=""):
        for item in self.tree_products.get_children():
            self.tree_products.delete(item)
        products = self.db.get_products(search_query)
        self.product_data_map.clear()
        product_names_for_combo = []
        low_stock_products = []
        for prod in products:
            prod_id = prod[0]
            prod_name = prod[1]
            # Ensure price fields are converted to Decimal for consistency
            # If the database adapter/converter is working, these should already be Decimals.
            # Adding Decimal() cast here as a safeguard if they were still strings/floats.
            import_price = Decimal(prod[3])
            selling_price = Decimal(prod[4])
            quantity = prod[5]
            supplier = prod[6]
            date_added = prod[7]

            self.product_data_map[prod_id] = {
                'name': prod_name,
                'category': prod[2],
                'import_price': import_price,
                'selling_price': selling_price,
                'quantity': quantity,
                'supplier': supplier,
                'date_added': date_added
            }
            self.tree_products.insert('', 'end', values=(
                prod_id, prod_name, prod[2], f"{import_price:.2f}", f"{selling_price:.2f}", quantity, supplier, date_added
            ))
            product_names_for_combo.append(f"{prod_id} - {prod_name}")

            if quantity <= 5 and quantity > 0: # Threshold for low stock
                low_stock_products.append(prod_name)
            elif quantity == 0:
                low_stock_products.append(f"{prod_name} (OUT OF STOCK)")


        self.combo_product['values'] = product_names_for_combo
        if product_names_for_combo:
            self.combo_product.set(product_names_for_combo[0]) # Set first item as default
            self.on_product_select_in_cart() # Update stock and price labels for default

        if low_stock_products:
            messagebox.showwarning("Low Stock Alert!",
                                   f"The following products are running low on stock: {', '.join(low_stock_products)}")

    def search_products(self):
        query = self.entry_search_product.get()
        self.load_products(query)

    def clear_search(self):
        self.entry_search_product.delete(0, tk.END)
        self.load_products()

    def add_product(self):
        name = self.entry_name.get()
        category = self.entry_category.get()
        import_price = self.entry_import_price.get()
        selling_price = self.entry_selling_price.get()
        quantity = self.entry_quantity.get()
        supplier = self.entry_supplier.get()

        if not all([name, import_price, selling_price, quantity]):
            messagebox.showwarning("Input Error", "Name, Import Price, Selling Price, and Quantity are required.")
            return

        try:
            quantity = int(quantity)
            if quantity < 0:
                messagebox.showwarning("Invalid Input", "Quantity cannot be negative.")
                return
            # Prices will be converted to Decimal in db.add_product
        except ValueError:
            messagebox.showwarning("Invalid Input", "Quantity must be an integer.")
            return

        product_id = self.db.add_product(name, category, import_price, selling_price, quantity, supplier)
        if product_id:
            messagebox.showinfo("Success", "Product added successfully!")
            self.clear_product_fields()
            self.load_products()
            self.generate_product_qr_code(product_id, name, category, selling_price)

    def update_product(self):
        selected_item = self.tree_products.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a product to update.")
            return

        product_id = self.tree_products.item(selected_item)['values'][0]
        name = self.entry_name.get()
        category = self.entry_category.get()
        import_price = self.entry_import_price.get()
        selling_price = self.entry_selling_price.get()
        quantity = self.entry_quantity.get()
        supplier = self.entry_supplier.get()

        if not all([name, import_price, selling_price, quantity]):
            messagebox.showwarning("Input Error", "Name, Import Price, Selling Price, and Quantity are required.")
            return

        try:
            quantity = int(quantity)
            if quantity < 0:
                messagebox.showwarning("Invalid Input", "Quantity cannot be negative.")
                return
        except ValueError:
            messagebox.showwarning("Invalid Input", "Quantity must be an integer.")
            return

        if self.db.update_product(product_id, name, category, import_price, selling_price, quantity, supplier):
            messagebox.showinfo("Success", "Product updated successfully!")
            self.clear_product_fields()
            self.load_products()
            self.generate_product_qr_code(product_id, name, category, selling_price)
#DALY
    def delete_product(self):
        selected_item = self.tree_products.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select a product to delete.")
            return

        product_id = self.tree_products.item(selected_item)['values'][0]
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete product ID {product_id}?"):
            if self.db.delete_product(product_id):
                messagebox.showinfo("Success", "Product deleted successfully!")
                self.clear_product_fields()
                self.load_products()

    def on_product_select(self, event=None):
        selected_item = self.tree_products.focus()
        if selected_item:
            values = self.tree_products.item(selected_item)['values']
            self.entry_name.delete(0, tk.END)
            self.entry_name.insert(0, values[1])
            self.entry_category.delete(0, tk.END)
            self.entry_category.insert(0, values[2])
            self.entry_import_price.delete(0, tk.END)
            self.entry_import_price.insert(0, values[3])
            self.entry_selling_price.delete(0, tk.END)
            self.entry_selling_price.insert(0, values[4])
            self.entry_quantity.delete(0, tk.END)
            self.entry_quantity.insert(0, values[5])
            self.entry_supplier.delete(0, tk.END)
            self.entry_supplier.insert(0, values[6])
        else:
            self.clear_product_fields()

    def clear_product_fields(self):
        self.entry_name.delete(0, tk.END)
        self.entry_category.delete(0, tk.END)
        self.entry_import_price.delete(0, tk.END)
        self.entry_selling_price.delete(0, tk.END)
        self.entry_quantity.delete(0, tk.END)
        self.entry_supplier.delete(0, tk.END)

    # --- Cart & Checkout Functions ---
    def on_product_select_in_cart(self, event=None):
        selected_product_str = self.combo_product.get()
        if selected_product_str:
            try:
                prod_id = int(selected_product_str.split(" - ")[0])
                product_info = self.product_data_map.get(prod_id)
                if product_info:
                    self.label_available_stock.config(text=f"Available Stock: {product_info['quantity']}")
                    # Ensure selling_price is formatted as Decimal for display
                    self.label_selected_price.config(text=f"Price: {product_info['selling_price']:.2f}")
                else:
                    self.label_available_stock.config(text="Available Stock: -")
                    self.label_selected_price.config(text="Price: -")
            except (ValueError, IndexError):
                self.label_available_stock.config(text="Available Stock: -")
                self.label_selected_price.config(text="Price: -")


    def add_to_cart(self):
        selected_product_str = self.combo_product.get()
        if not selected_product_str:
            messagebox.showwarning("Warning", "Please select a product to add to cart.")
            return

        try:
            prod_id = int(selected_product_str.split(" - ")[0])
            qty_to_add = int(self.entry_qty.get())

            if qty_to_add <= 0:
                messagebox.showwarning("Invalid Quantity", "Quantity must be a positive number.")
                return

            product_info = self.product_data_map.get(prod_id)
            if not product_info:
                messagebox.showerror("Error", "Selected product not found in inventory.")
                return

            available_qty = product_info['quantity']
            if qty_to_add > available_qty:
                messagebox.showwarning("Insufficient Stock",
                                       f"Only {available_qty} units of '{product_info['name']}' available.")
                return

            product_name = product_info['name']
            selling_price = product_info['selling_price'] # This is a Decimal from product_data_map

            # Calculate total_price using Decimal for precision
            total_price = Decimal(qty_to_add) * selling_price

            # Check if product is already in cart, then update quantity
            found_in_cart = False
            for i, item in enumerate(self.cart):
                if item[0] == prod_id: # item[0] is product_id
                    new_qty = item[2] + qty_to_add
                    new_total = Decimal(new_qty) * selling_price # Ensure consistent Decimal operation
                    self.cart[i] = (prod_id, product_name, new_qty, selling_price, new_total)
                    found_in_cart = True
                    break

            if not found_in_cart:
                self.cart.append((prod_id, product_name, qty_to_add, selling_price, total_price))

            self.update_cart_display_and_total()
            messagebox.showinfo("Cart Update", f"{qty_to_add} x '{product_name}' added to cart.")
            self.entry_qty.delete(0, tk.END)
            self.entry_qty.insert(0, "1")
            self.on_product_select_in_cart() # Refresh available stock label
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid numeric quantity.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while adding to cart: {str(e)}")

                                   
    def update_cart_display_and_total(self):
        for item in self.tree_cart.get_children():
            self.tree_cart.delete(item)
        total_cart_amount = Decimal('0.00') # Initialize as Decimal for accurate sum
        for item in self.cart:
            # item is (prod_id, product_name, qty, unit_price (Decimal), total_price (Decimal))
            self.tree_cart.insert('', 'end', values=(item[0], item[1], item[2], f"{item[3]:.2f}", f"{item[4]:.2f}"))
            total_cart_amount += item[4] # Add Decimal values

        self.label_cart_total.config(text=f"Cart Total: {total_cart_amount:.2f}")

    def remove_from_cart(self):
        selected_item = self.tree_cart.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select an item in the cart to remove.")
            return

        item_values = self.tree_cart.item(selected_item)['values']
        prod_id_to_remove = item_values[0] # Get the product ID from the Treeview

        # Find and remove the item from the self.cart list
        for i, item in enumerate(self.cart):
            if item[0] == prod_id_to_remove:
                del self.cart[i]
                break
        self.update_cart_display_and_total()
        messagebox.showinfo("Cart Update", f"'{item_values[1]}' removed from cart.")
        self.on_product_select_in_cart() # Refresh available stock label

    def update_cart_item_quantity(self):
        selected_item = self.tree_cart.focus()
        if not selected_item:
            messagebox.showwarning("Selection Error", "Please select an item in the cart to update its quantity.")
            return

        item_values = self.tree_cart.item(selected_item)['values']
        prod_id = item_values[0]
        current_name = item_values[1]
        current_unit_price = Decimal(item_values[3]) # Already a Decimal from our storage

        new_qty_str = simpledialog.askstring("Update Quantity", f"Enter new quantity for '{current_name}':",
                                                initialvalue=str(item_values[2]))
        if new_qty_str is None: # User cancelled
            return

        try:
            new_qty = int(new_qty_str)
            if new_qty <= 0:
                messagebox.showwarning("Invalid Quantity", "Quantity must be a positive number.")
                return

            product_info = self.product_data_map.get(prod_id)
            if not product_info:
                messagebox.showerror("Error", "Product not found in inventory.")
                return

            available_qty = product_info['quantity']
            if new_qty > available_qty:
                messagebox.showwarning("Insufficient Stock",
                                       f"Only {available_qty} units of '{current_name}' available. Cannot set quantity to {new_qty}.")
                return

            # Update the quantity and total price in the cart list
            for i, item in enumerate(self.cart):
                if item[0] == prod_id:
                    new_total_price = Decimal(new_qty) * current_unit_price
                    self.cart[i] = (prod_id, current_name, new_qty, current_unit_price, new_total_price)
                    break
            self.update_cart_display_and_total()
            messagebox.showinfo("Cart Update", f"Quantity of '{current_name}' updated to {new_qty}.")
            self.on_product_select_in_cart() # Refresh available stock label

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid numeric quantity.")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while updating cart item: {str(e)}")

    def on_cart_item_select(self, event=None):
        # This function can be used to display details of selected cart item if needed.
        # Currently, it's primarily used for selecting an item for removal/quantity update.
        pass

    def clear_cart(self):
        if messagebox.askyesno("Clear Cart", "Are you sure you want to clear all items from the cart?"):
            self.cart.clear()
            self.update_cart_display_and_total()
            messagebox.showinfo("Cart Cleared", "All items removed from cart.")
            self.on_product_select_in_cart() # Refresh available stock label

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty Cart", "The cart is empty. Please add products before checking out.")
            return

        # Calculate total_amount for display in confirmation, ensuring Decimal sum
        current_cart_total = sum(item[4] for item in self.cart) # item[4] is already a Decimal

        if messagebox.askyesno("Confirm Checkout", f"Confirm sale for total: {current_cart_total:.2f}?"):
            try:
                # Pass the cart items to the database manager for recording
                if self.db.record_sale(self.cart):
                    messagebox.showinfo("Sale Successful", "Sale recorded successfully!")
                    self.cart.clear() # Clear the cart
                    self.update_cart_display_and_total()
                    self.load_products() # Reload products to reflect updated quantities
                    self.load_sales_history() # Reload sales history
                    self.update_income_expenses() # Update income/expenses
                else:
                    messagebox.showerror("Checkout Failed", "Failed to record sale in database.")
            except Exception as e:
                messagebox.showerror("Checkout Error", f"Failed to record sale: {str(e)}")

    # --- Income & Expenses Functions ---
    def add_expense(self):
        description = self.entry_expense_desc.get()
        amount = self.entry_expense_amount.get()

        if not description or not amount:
            messagebox.showwarning("Input Error", "Description and Amount are required for expenses.")
            return

        try:
            # Amount will be converted to Decimal in db.add_expense
            if self.db.add_expense(description, amount):
                messagebox.showinfo("Success", "Expense added successfully!")
                self.entry_expense_desc.delete(0, tk.END)
                self.entry_expense_amount.delete(0, tk.END)
                self.update_income_expenses()
            else:
                messagebox.showerror("Error", "Failed to add expense.")
        except ValueError:
            messagebox.showwarning("Invalid Input", "Expense amount must be a valid number.")

    def update_income_expenses(self, event=None): # Added event=None for binding
        selected_period = self.period_var.get()
        selected_date_str = self.date_entry.get()

        try:
            # Validate the date string only if not 'all' period
            if selected_period != "all":
                # Attempt to parse the date to ensure it's valid
                datetime.strptime(selected_date_str, '%Y-%m-%d')
            
            income = self.db.get_sales_sum_by_period(selected_period, selected_date_str)
            expenses = self.db.get_expenses_sum_by_period(selected_period, selected_date_str) 
            net_profit = income - expenses

            self.label_total_income.config(text=f"Total Income ({selected_period.capitalize()}): {income:.2f}")
            self.label_total_expenses.config(text=f"Total Expenses ({selected_period.capitalize()}): {expenses:.2f}")
            self.label_net_profit.config(text=f"Net Profit ({selected_period.capitalize()}): {net_profit:.2f}")
            
            self.load_expense_history(selected_period, selected_date_str) # Load expenses for the selected period

        except ValueError:
            messagebox.showerror("Invalid Date", "Please enter a date in YYYY-MM-DD format.")
            # Reset date entry and period if date is invalid for a specific period
            if selected_period != "all":
                 self.date_entry.delete(0, tk.END)
                 self.date_entry.insert(0, datetime.now().strftime('%Y-%m-%d')) # Reset to today
                 self.period_var.set("day") # Reset period to "day"
            self.update_income_expenses() # Recalculate with corrected date/period
        except Exception as e:
            messagebox.showerror("Calculation Error", f"An error occurred updating income/expenses: {e}")

    def load_expense_history(self, period="all", date_value_str=""):
        for item in self.tree_expense_history.get_children():
            self.tree_expense_history.delete(item)
        
        expenses = self.db.get_expenses_by_period(period, date_value_str)
        for expense in expenses:
            amount = Decimal(expense[2]) if expense[2] else Decimal('0.00')
            self.tree_expense_history.insert('', 'end', values=(
                expense[0], expense[1], f"{amount:.2f}", expense[3]
            ))


    # --- Sales History Functions ---
    def load_sales_history(self):
        for item in self.tree_sales_history.get_children():
            self.tree_sales_history.delete(item)
        sales = self.db.get_sales_history()
        for sale in sales:
            # Ensure price fields are formatted for display
            unit_price = Decimal(sale[4]) if sale[4] else Decimal('0.00')
            total_price = Decimal(sale[5]) if sale[5] else Decimal('0.00')
            self.tree_sales_history.insert('', 'end', values=(
                sale[0], sale[2], sale[3], f"{unit_price:.2f}", f"{total_price:.2f}", sale[6]
            ))


if __name__ == "__main__":
    if THEME_AVAILABLE:
        root = tb.Window(themename="minty")
    else:
        root = tk.Tk()
    app = MiniMartApp(root)
    root.mainloop()
    if app.db.conn:
        app.db.close()

# Add a style for large buttons if not using ttkbootstrap
if not THEME_AVAILABLE:
    s = ttk.Style()
    s.configure("Large.TButton", font=("Comic Sans MS", 14, "bold"), padding=8)