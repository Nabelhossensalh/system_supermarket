import sqlite3
from models import Product, Sale


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("grocery_store.db", check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # جدول المنتجات
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS products 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             name TEXT, 
             price REAL, 
             barcode TEXT UNIQUE, 
             quantity INTEGER)"""
        )
        # جدول المبيعات
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS sales 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             date TEXT, 
             total REAL, 
             type TEXT, 
             customer TEXT)"""
        )
        self.conn.commit()

        # إضافة عمود "مدفوع" للديون (إذا لم يكن موجوداً)
        try:
            cursor.execute("ALTER TABLE sales ADD COLUMN paid INTEGER DEFAULT 0")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # العمود موجود مسبقاً

    # =============================================
    #  عمليات المنتجات
    # =============================================
    def add_product(self, p: Product):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO products (name, price, barcode, quantity) VALUES (?, ?, ?, ?)",
                (p.name, p.price, p.barcode, p.quantity),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def get_all_products(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products ORDER BY name")
        return [
            Product(id=r[0], name=r[1], price=r[2], barcode=r[3], quantity=r[4])
            for r in cursor.fetchall()
        ]

    def get_product_by_barcode(self, barcode):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM products WHERE barcode = ?", (barcode,))
        r = cursor.fetchone()
        if r:
            return Product(id=r[0], name=r[1], price=r[2], barcode=r[3], quantity=r[4])
        return None

    def update_product(self, product_id, name, price, barcode, quantity):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "UPDATE products SET name=?, price=?, barcode=?, quantity=? WHERE id=?",
                (name, price, barcode, quantity, product_id),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def delete_product(self, product_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.conn.commit()

    def update_stock(self, barcode, qty_sold):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE products SET quantity = quantity - ? WHERE barcode = ?",
            (qty_sold, barcode),
        )
        self.conn.commit()

    def get_low_stock_products(self, threshold=3):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM products WHERE quantity <= ? ORDER BY quantity",
            (threshold,),
        )
        return [
            Product(id=r[0], name=r[1], price=r[2], barcode=r[3], quantity=r[4])
            for r in cursor.fetchall()
        ]

    # =============================================
    #  عمليات المبيعات
    # =============================================
    def add_sale(self, s: Sale):
        cursor = self.conn.cursor()
        paid = 1 if s.type == "cash" else 0
        cursor.execute(
            "INSERT INTO sales (date, total, type, customer, paid) VALUES (?, ?, ?, ?, ?)",
            (s.date, s.total, s.type, s.customer, paid),
        )
        self.conn.commit()

    def get_daily_reports(self, date_str):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT SUM(total), type FROM sales WHERE date = ? GROUP BY type",
            (date_str,),
        )
        return cursor.fetchall()

    def get_total_items_sold(self, date_str):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sales WHERE date = ?", (date_str,))
        result = cursor.fetchone()
        return result[0] if result else 0

    def get_all_sales(self, date_str=None):
        cursor = self.conn.cursor()
        if date_str:
            cursor.execute(
                "SELECT id, date, total, type, customer, paid FROM sales WHERE date = ? ORDER BY id DESC",
                (date_str,),
            )
        else:
            cursor.execute(
                "SELECT id, date, total, type, customer, paid FROM sales ORDER BY id DESC"
            )
        return cursor.fetchall()

    # =============================================
    #  عمليات الديون
    # =============================================
    def get_unpaid_debts(self):
        """جلب جميع الديون غير المسددة"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, date, total, customer FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0) ORDER BY date DESC"
        )
        return cursor.fetchall()

    def get_debts_by_customer(self):
        """تجميع الديون حسب اسم الزبون"""
        cursor = self.conn.cursor()
        cursor.execute(
            """SELECT customer, SUM(total) as total_debt, COUNT(*) as num_transactions 
               FROM sales 
               WHERE type='debt' AND (paid IS NULL OR paid=0) 
               GROUP BY customer 
               ORDER BY total_debt DESC"""
        )
        return cursor.fetchall()

    def get_customer_debts_detail(self, customer_name):
        """تفاصيل ديون زبون محدد"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, date, total FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0) AND customer=? ORDER BY date DESC",
            (customer_name,),
        )
        return cursor.fetchall()

    def mark_debt_paid(self, sale_id):
        """تسجيل سداد دين"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE sales SET paid = 1 WHERE id = ?", (sale_id,))
        self.conn.commit()

    def mark_customer_debts_paid(self, customer_name):
        """تسجيل سداد جميع ديون زبون"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE sales SET paid = 1 WHERE type='debt' AND customer = ? AND (paid IS NULL OR paid=0)",
            (customer_name,),
        )
        self.conn.commit()

    def get_total_unpaid_debts(self):
        """إجمالي الديون غير المسددة"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0)"
        )
        return cursor.fetchone()[0]

    def get_total_cash(self):
        """إجمالي النقد المحصّل (كل الأيام)"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='cash'")
        return cursor.fetchone()[0]

    def get_paid_debts_total(self):
        """إجمالي الديون المسددة"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='debt' AND paid=1"
        )
        return cursor.fetchone()[0]
