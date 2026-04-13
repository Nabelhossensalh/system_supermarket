import sqlite3
import flet as ft
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import time

# =============================================================================
#  نماذج البيانات (Models)
# =============================================================================
@dataclass
class Product:
    id: Optional[int] = None
    name: str = ""
    price: float = 0.0
    barcode: str = ""
    quantity: int = 0

@dataclass
class Sale:
    id: Optional[int] = None
    date: str = ""
    total: float = 0.0
    type: str = "cash"  # cash or debt
    customer: str = ""

# =============================================================================
#  إدارة قاعدة البيانات (Database)
# =============================================================================
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

    # --- عمليات المنتجات ---
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

    # --- عمليات المبيعات ---
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

    # --- عمليات الديون ---
    def get_unpaid_debts(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, date, total, customer FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0) ORDER BY date DESC"
        )
        return cursor.fetchall()

    def get_debts_by_customer(self):
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
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT id, date, total FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0) AND customer=? ORDER BY date DESC",
            (customer_name,),
        )
        return cursor.fetchall()

    def mark_debt_paid(self, sale_id):
        cursor = self.conn.cursor()
        cursor.execute("UPDATE sales SET paid = 1 WHERE id = ?", (sale_id,))
        self.conn.commit()

    def mark_customer_debts_paid(self, customer_name):
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE sales SET paid = 1 WHERE type='debt' AND customer = ? AND (paid IS NULL OR paid=0)",
            (customer_name,),
        )
        self.conn.commit()

    def get_total_unpaid_debts(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='debt' AND (paid IS NULL OR paid=0)"
        )
        return cursor.fetchone()[0]

    def get_total_cash(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='cash'")
        return cursor.fetchone()[0]

    def get_paid_debts_total(self):
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COALESCE(SUM(total), 0) FROM sales WHERE type='debt' AND paid=1"
        )
        return cursor.fetchone()[0]


class AppUI:
    def __init__(self, page: ft.Page):
        self.page = page
        self.db = Database()
        self.cart = {}  # {barcode: {'product': Product, 'qty': int}}

        # إعدادات الصفحة
        self.page.title = "نظام بقالة ذكية     | POS"
        self.page.bgcolor="#F4F7FC"
        self.page.rtl = True
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.window.width = 350
        self.page.window.height = 750
        self.page.theme = ft.Theme(font_family="Cairo")

        # إعدادات الصفحة والبحث
        self.current_page = "home"
        self.target_barcode_field = None

        # عناصر POS
        self.cart_list_view = ft.ListView(expand=True, spacing=5, padding=10)
        self.total_text = ft.Text("0.00", size=32, weight="bold", color="#1A73E8")
        self.search_list_view = ft.ListView(height=150, visible=False, padding=5)

        self.show_home()

    # =============================================
    #  منطق البحث والمسح (متوافق مع أندرويد)
    # =============================================
    def start_camera(self, target_field):
        """
        بما أن مكتبات cv2 و pyzbar غير مرغوبة، وبما أن Flet لا تدعم مسح الكاميرا مباشرة،
        أفضل طريقة في أندرويد هي استخدام تطبيق ماسح باركود خارجي يقوم بإدخال النتيجة تلقائياً.
        أو يمكننا استخدام الكاميرا لالتقاط صورة (FilePicker).
        """
        self.target_barcode_field = target_field
        self.show_message("يرجى استخدام ماسح الباركود الخارجي أو كتابة الكود يدوياً", "info")
        if self.target_barcode_field:
            self.target_barcode_field.focus()
            self.page.update()

    def stop_camera(self):
        pass

    def _handle_scanned_code(self, code):
        if self.target_barcode_field:
            self.target_barcode_field.value = code
        if self.current_page == "pos":
            self.add_to_cart(code)
        self.show_message(f"تم مسح: {code}", "green")

    def stop_camera(self):
        self.pc_camera_running = False

    # =============================================
    #  رسالة تنبيه بسيطة
    # =============================================
    def show_message(self, text, color="green"):
        snack = ft.SnackBar(content=ft.Text(text, color="white"), bgcolor=color)
        self.page.overlay.append(snack)
        snack.open = True
        try:
            self.page.update()
        except Exception:
            pass

    # =============================================
    #  الصفحة الرئيسية
    # =============================================
    def show_home(self, e=None):
        self.stop_camera()
        self.current_page = "home"
        self.cart = {}
        self.page.clean()
        self.page.add(
            ft.Container(
                expand=True,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_right,
                    end=ft.alignment.bottom_left,
                    colors=["#1565C0", "#0D47A1"],
                ),
                padding=ft.padding.symmetric(horizontal=30),
                content=ft.Column(
                    [
                        ft.Container(height=60),
                        ft.Icon(ft.Icons.STOREFRONT, size=80, color="white"),
                        ft.Container(height=10),
                        ft.Text("نظام البقالة الذكي", size=32, color="", weight="bold", text_align="center"),
                        ft.Text("إدارة المبيعات والمخزون", size=16, color="#BBDEFB", text_align="center"),
                        ft.Container(height=50),
                        # بطاقات القائمة
                        self._menu_card("بدء عملية بيع", "ابحث عن المنتج وأضفه للسلة", ft.Icons.POINT_OF_SALE, "#4CAF50", self.show_pos),
                        self._menu_card("إضافة منتج جديد", "سجل منتج جديد في المخزون", ft.Icons.INVENTORY_2, "#FF9800", self.show_inventory),
                        self._menu_card("عرض المنتجات", "تصفح جميع المنتجات المسجلة", ft.Icons.LIST_ALT, "#2196F3", self.show_products_list),
                        self._menu_card("التقارير والإدارة", "مبيعات، ديون، وتنبيهات المخزون", ft.Icons.LEADERBOARD, "#E91E63", self.show_reports),
                        self._menu_card("الملاحظات والدعم", "راسلنا مباشرة عبر الواتساب", ft.Icons.CHAT, "#25D366", self._show_notes_dialog),
                        ft.Container(expand=True),
                        ft.Text("V 1.5 | نظام بقالة ذكي", color="#90CAF9", size=11, text_align="center"),
                        ft.Container(height=15),
                    ],
                    horizontal_alignment="center",
                ),
            )
        )

    def _menu_card(self, title, subtitle, icon, color, on_click):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color="white", size=24),
                        bgcolor=color,
                        width=45,
                        height=45,
                        border_radius=12,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(width=12),
                    ft.Column(
                        [
                            ft.Text(title, size=17, weight="w600", color="#333"),
                            ft.Text(subtitle, size=12, color="#999"),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_LEFT, color="#CCC", size=20),
                ]
            ),
            padding=18,
            margin=ft.margin.only(bottom=12),
            bgcolor="white",
            border_radius=14,
            shadow=ft.BoxShadow(blur_radius=8, color="#18000000"),
            on_click=on_click,
        )

    # =============================================
    #  واجهة الملاحظات والمراسلة
    # =============================================
    def _show_notes_dialog(self, e):
        note_field = ft.TextField(
            label="اكتب ملاحظتك هنا",
            multiline=True,
            min_lines=3,
            max_lines=5,
            hint_text="مثال: واجهت مشكلة في مسح الباركود، أو اقتراح لتطوير النظام..."
        )

        def send_whatsapp(ev):
            msg = note_field.value.strip()
            if not msg:
                self.show_message("يرجى كتابة ملاحظة أولاً", "orange")
                return
            
            # رقم الواتساب مع رمز الدولة (افتراضي اليمن +967)
            phone = "967779610798"
            url = f"https://wa.me/{phone}/?text={msg}"
            self.page.launch_url(url)
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.CHAT, color="#25D366"), ft.Text("إرسال ملاحظة")]),
            content=ft.Column([
                ft.Text("سيتم تحويلك لتطبيق الواتساب لمراسلة الدعم الفني بالرقم 779610798", size=13, color="#666"),
                note_field
            ], tight=True),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: (setattr(dlg, 'open', False), self.page.update())),
                ft.ElevatedButton("إرسال عبر واتساب", icon=ft.Icons.SEND, bgcolor="#25D366", color="white", on_click=send_whatsapp),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # =============================================
    #  صفحة نقطة البيع POS
    # =============================================
    def show_pos(self, e=None):
        self.current_page = "pos"
        self.cart = {}
        self.page.clean()

        # حقل البحث / الباركود
        self.pos_input = ft.TextField(
            label="🔍 ابحث عن منتج بالاسم أو رقم الباركود",
            hint_text="مثال: حليب، أرز، أو امسح الباركود بالكاميرا...",
            prefix_icon=ft.Icons.SEARCH,
            suffix=ft.IconButton(
                ft.Icons.CAMERA_ALT,
                on_click=lambda _: self.start_camera(self.pos_input),
                tooltip="📷 اضغط هنا لفتح الكاميرا ومسح الباركود",
            ),
            on_change=self._on_pos_search,
            on_submit=self._on_pos_submit,
            border_radius=12,
            filled=True,
            autofocus=True,
        )

        self.cart_list_view.controls.clear()
        self.total_text.value = "0.00"
        self.search_list_view.controls.clear()
        self.search_list_view.visible = False

        self.page.add(
            ft.AppBar(
                title=ft.Text("عملية بيع جديدة"),
                bgcolor="#1565C0",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_home, icon_color="white", tooltip="رجوع للقائمة الرئيسية"),
            ),
            # تعليمات سريعة للمستخدم
            ft.Container(
                padding=ft.padding.symmetric(horizontal=12, vertical=6),
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, color="#1565C0", size=16),
                        ft.Text("ابحث بالاسم أو امسح الباركود بالكاميرا لإضافة المنتجات للسلة", size=12, color="#1565C0"),
                    ],
                    spacing=5,
                ),
                bgcolor="#E3F2FD",
                border_radius=8,
                margin=ft.margin.only(left=10, right=10, top=5),
            ),
            ft.Container(padding=10, content=self.pos_input),
            self.search_list_view,
            ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.SHOPPING_CART, color="#555", size=18),
                                ft.Text("سلة المشتريات:", size=16, weight="bold", color="#555"),
                                ft.Container(expand=True),
                                ft.Text("اضغط + أو - لتعديل الكمية", size=11, color="#AAA"),
                            ]
                        ),
                        self.cart_list_view,
                    ]
                ),
                expand=True,
                bgcolor="white",
                border_radius=15,
                margin=10,
                padding=15,
            ),
            # شريط الإجمالي والدفع
            ft.Container(
                padding=15,
                bgcolor="#FAFAFA",
                border=ft.border.only(top=ft.BorderSide(1, "#E0E0E0")),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.RECEIPT, color="#333", size=22),
                                ft.Text("الإجمالي:", size=20, weight="bold"),
                                ft.Container(expand=True),
                                self.total_text,
                                ft.Text(" ج.س", size=18, color="#888"),
                            ]
                        ),
                        ft.Container(height=5),
                        ft.Text("اختر طريقة الدفع لإتمام العملية:", size=12, color="#999"),
                        ft.Container(height=5),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "💵 دفع نقدي",
                                    icon=ft.Icons.PAYMENTS,
                                    bgcolor="#4CAF50",
                                    color="white",
                                    expand=True,
                                    height=50,
                                    on_click=lambda _: self._complete_sale("cash"),
                                    tooltip="اضغط لإتمام البيع نقداً",
                                ),
                                ft.Container(width=10),
                                ft.ElevatedButton(
                                    "📝 تسجيل دين",
                                    icon=ft.Icons.PERSON_ADD,
                                    bgcolor="#FF9800",
                                    color="white",
                                    expand=True,
                                    height=50,
                                    on_click=self._ask_debt_name,
                                    tooltip="اضغط لتسجيل المبلغ كدين على زبون",
                                ),
                            ]
                        ),
                    ]
                ),
            ),
        )

    def _on_pos_search(self, e):
        """البحث الذكي أثناء الكتابة - يعرض نتائج بالاسم (حتى لو كلمات متفرقة) أو الباركود"""
        query = e.control.value.strip().lower()
        if len(query) < 1:
            self.search_list_view.visible = False
            self.page.update()
            return

        # تقسيم جملة البحث لكلمات للبحث في كل كلمة على حدة
        query_words = query.split()
        products = self.db.get_all_products()
        
        matches = []
        for p in products:
            p_name_lower = p.name.lower()
            p_barcode = p.barcode.lower()
            
            # التحقق إذا كانت كل كلمات البحث موجودة في الاسم أو الباركود
            match_found = all(word in p_name_lower for word in query_words) or query in p_barcode
            if match_found:
                matches.append(p)

        self.search_list_view.controls.clear()
        for p in matches[:6]:
            is_out = p.quantity <= 0
            stock_color = "#E53935" if is_out else ("#FF9800" if p.quantity <= 3 else "#4CAF50")
            stock_label = "❌ نفد" if is_out else (f"⚠️ متبقي {p.quantity}" if p.quantity <= 3 else f"✅ متوفر")
            
            self.search_list_view.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.SHOPPING_BAG, color="#CCC" if is_out else "#1565C0", size=24),
                            ft.Column(
                                [
                                    # التغيير هنا: التأكد من ظهور الاسم بوضوح ولون أسود
                                    ft.Text(p.name, weight="bold", size=16, color="black" if not is_out else "#999"),
                                    ft.Row(
                                        [
                                            ft.Text(f"السعر: {p.price} ج.س", size=13, color="#555"),
                                            ft.Container(
                                                content=ft.Text(stock_label, size=11, color="white", weight="bold"),
                                                bgcolor=stock_color,
                                                border_radius=6,
                                                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                                            ),
                                        ],
                                        spacing=10,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(f"{p.price} ج.س", weight="bold", size=16, color="#1565C0" if not is_out else "#CCC"),
                        ],
                        alignment="center",
                    ),
                    padding=12,
                    border_radius=10,
                    bgcolor="white" if not is_out else "#FAFAFA",
                    border=ft.border.all(1, "#EEEEEE"),
                    on_click=None if is_out else (lambda _, prod=p: self._select_from_search(prod)),
                    opacity=0.7 if is_out else 1.0,
                )
            )

        self.search_list_view.visible = len(matches) > 0
        try:
            self.search_list_view.update()
            self.page.update()
        except:
            pass

    def _on_pos_submit(self, e):
        """عند الضغط على Enter - يبحث بالباركود مباشرة ويضيف للسلة"""
        barcode = e.control.value.strip()
        if barcode:
            self.add_to_cart(barcode)
            e.control.value = ""
            self.search_list_view.visible = False
            e.control.focus()
            self.page.update()

    def _select_from_search(self, product):
        """عند اختيار منتج من قائمة البحث"""
        self.add_to_cart(product.barcode)
        self.pos_input.value = ""
        self.search_list_view.visible = False
        self.pos_input.focus()
        self.page.update()

    # =============================================
    #  منطق السلة
    # =============================================
    def add_to_cart(self, barcode):
        """إضافة منتج للسلة بواسطة الباركود"""
        products = self.db.get_all_products()
        p = next((x for x in products if x.barcode == barcode), None)

        if not p:
            self.show_message("❌ المنتج غير موجود في النظام!", "red")
            return

        if p.quantity <= 0:
            self._show_out_of_stock_alert(p.name)
            return

        if barcode in self.cart:
            current_qty = self.cart[barcode]["qty"]
            if current_qty >= p.quantity:
                self._show_stock_limit_alert(p.name, p.quantity)
                return
            self.cart[barcode]["qty"] += 1
        else:
            self.cart[barcode] = {"product": p, "qty": 1}

        self.show_message(f"✅ تمت إضافة: {p.name} (متبقي: {p.quantity - self.cart[barcode]['qty']})", "#4CAF50")
        self._refresh_cart_ui()

    def _show_out_of_stock_alert(self, product_name):
        """نافذة تنبيه واضحة عند نفاد المخزون"""
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR, color="#E53935", size=30),
                    ft.Text("⚠️ نفد المخزون!", color="#E53935", weight="bold", size=20),
                ]
            ),
            content=ft.Column(
                [
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Icon(ft.Icons.REMOVE_SHOPPING_CART, color="#E53935", size=50),
                                ft.Container(height=10),
                                ft.Text(
                                    f"المنتج '{product_name}' انتهى من المخزون تماماً!",
                                    size=16, weight="bold", text_align="center",
                                ),
                                ft.Container(height=5),
                                ft.Text(
                                    "يرجى إعادة تعبئة المخزون من صفحة إدارة المنتجات قبل البيع.",
                                    size=13, color="#777", text_align="center",
                                ),
                            ],
                            horizontal_alignment="center",
                        ),
                        padding=20,
                        bgcolor="#FFEBEE",
                        border_radius=12,
                    ),
                ],
                tight=True,
            ),
            actions=[
                ft.ElevatedButton(
                    "حسناً، فهمت",
                    bgcolor="#E53935",
                    color="white",
                    on_click=lambda _: (setattr(dlg, 'open', False), self.page.update()),
                ),
            ],
            actions_alignment="center",
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _show_stock_limit_alert(self, product_name, available_qty):
        """نافذة تنبيه عند الوصول لحد المخزون المتاح"""
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, color="#FF9800", size=28),
                    ft.Text("الكمية غير كافية", color="#FF9800", weight="bold", size=18),
                ]
            ),
            content=ft.Column(
                [
                    ft.Text(
                        f"المنتج '{product_name}' متبقي منه {available_qty} فقط في المخزون.",
                        size=15, text_align="center",
                    ),
                    ft.Text(
                        "لا يمكن إضافة كمية أكثر من المتوفر.",
                        size=13, color="#999", text_align="center",
                    ),
                ],
                tight=True,
                horizontal_alignment="center",
            ),
            actions=[
                ft.ElevatedButton(
                    "حسناً",
                    bgcolor="#FF9800",
                    color="white",
                    on_click=lambda _: (setattr(dlg, 'open', False), self.page.update()),
                ),
            ],
            actions_alignment="center",
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _change_qty(self, barcode, delta):
        """تغيير كمية منتج في السلة"""
        if barcode not in self.cart:
            return
        self.cart[barcode]["qty"] += delta
        if self.cart[barcode]["qty"] <= 0:
            del self.cart[barcode]
        self._refresh_cart_ui()

    def _remove_from_cart(self, barcode):
        """حذف منتج من السلة"""
        if barcode in self.cart:
            del self.cart[barcode]
        self._refresh_cart_ui()

    def _refresh_cart_ui(self):
        """تحديث عرض السلة وحساب الإجمالي"""
        self.cart_list_view.controls.clear()
        total = 0.0

        if not self.cart:
            self.cart_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.ADD_SHOPPING_CART, color="#CCC", size=40),
                            ft.Text("السلة فارغة", size=16, color="#BBB", weight="bold"),
                            ft.Text("ابحث عن منتج أو امسح الباركود لإضافته هنا", size=12, color="#CCC"),
                        ],
                        horizontal_alignment="center",
                        spacing=5,
                    ),
                    padding=30,
                    alignment=ft.alignment.center,
                )
            )

        for barcode, item in self.cart.items():
            p = item["product"]
            qty = item["qty"]
            subtotal = p.price * qty
            total += subtotal
            remaining = p.quantity - qty
            remaining_color = "#E53935" if remaining <= 2 else "#999"

            self.cart_list_view.controls.append(
                ft.Container(
                    bgcolor="#F8F9FA",
                    padding=12,
                    border_radius=10,
                    margin=ft.margin.only(bottom=5),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    # اسم المنتج والسعر
                                    ft.Column(
                                        [
                                            ft.Text(p.name, weight="bold", size=15),
                                            ft.Text(f"💰 {p.price} ج.س للواحدة", size=12, color="#888"),
                                            ft.Text(f"📦 متبقي في المخزون: {remaining}", size=11, color=remaining_color),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    # أزرار التحكم بالكمية
                                    ft.IconButton(
                                        ft.Icons.REMOVE_CIRCLE,
                                        icon_color="#E53935",
                                        icon_size=22,
                                        on_click=lambda _, b=barcode: self._change_qty(b, -1),
                                        tooltip="تقليل الكمية بواحد",
                                    ),
                                    ft.Container(
                                        content=ft.Text(str(qty), size=18, weight="bold", text_align="center"),
                                        width=35,
                                        alignment=ft.alignment.center,
                                        tooltip="الكمية المطلوبة",
                                    ),
                                    ft.IconButton(
                                        ft.Icons.ADD_CIRCLE,
                                        icon_color="#43A047",
                                        icon_size=22,
                                        on_click=lambda _, b=barcode: self._change_qty(b, 1),
                                        tooltip="زيادة الكمية بواحد",
                                    ),
                                    ft.Container(width=5),
                                    # المجموع الفرعي
                                    ft.Column(
                                        [
                                            ft.Text("المجموع", size=10, color="#AAA"),
                                            ft.Text(f"{subtotal:.2f}", weight="bold", size=16, color="#1565C0"),
                                        ],
                                        horizontal_alignment="center",
                                        spacing=0,
                                    ),
                                    # زر الحذف
                                    ft.IconButton(
                                        ft.Icons.DELETE_OUTLINE,
                                        icon_color="#999",
                                        icon_size=20,
                                        on_click=lambda _, b=barcode: self._remove_from_cart(b),
                                        tooltip="🗑️ حذف المنتج من السلة",
                                    ),
                                ],
                                alignment="center",
                            ),
                        ]
                    ),
                )
            )

        self.total_text.value = f"{total:.2f}"
        self.page.update()

    # =============================================
    #  إتمام عملية البيع
    # =============================================
    def _complete_sale(self, sale_type, customer=""):
        if not self.cart:
            self.show_message("⚠️ السلة فارغة! أضف منتجات أولاً", "orange")
            return

        # التحقق من المخزون قبل إتمام البيع
        out_of_stock_items = []
        insufficient_items = []
        products = self.db.get_all_products()

        for barcode, item in self.cart.items():
            # جلب أحدث بيانات المنتج من قاعدة البيانات
            current_product = next((x for x in products if x.barcode == barcode), None)
            if current_product:
                if current_product.quantity <= 0:
                    out_of_stock_items.append(current_product.name)
                elif item["qty"] > current_product.quantity:
                    insufficient_items.append((current_product.name, current_product.quantity, item["qty"]))

        if out_of_stock_items:
            names = "، ".join(out_of_stock_items)
            self._show_sale_stock_error(
                "منتجات نفدت من المخزون!",
                f"المنتجات التالية انتهت من المخزون ولا يمكن إتمام البيع:\n\n{names}\n\nيرجى حذفها من السلة أو إعادة تعبئة المخزون.",
                "#E53935"
            )
            return

        if insufficient_items:
            details = "\n".join([f"• {name}: طلبت {req} لكن المتوفر {avail} فقط" for name, avail, req in insufficient_items])
            self._show_sale_stock_error(
                "الكمية المطلوبة أكثر من المتوفر!",
                f"{details}\n\nيرجى تقليل الكمية في السلة.",
                "#FF9800"
            )
            return

        total = sum(item["product"].price * item["qty"] for item in self.cart.values())

        # حفظ العملية
        self.db.add_sale(
            Sale(
                date=datetime.now().strftime("%Y-%m-%d"),
                total=total,
                type=sale_type,
                customer=customer,
            )
        )

        # تحديث المخزون
        for barcode, item in self.cart.items():
            self.db.update_stock(barcode, item["qty"])

        self.cart = {}
        if sale_type == "cash":
            self.show_message(f"✅ تم البيع بنجاح! الإجمالي: {total:.2f} ج.س", "#4CAF50")
        else:
            self.show_message(f"📝 تم تسجيل دين على '{customer}' بقيمة {total:.2f} ج.س", "#FF9800")
        self.show_home()

    def _show_sale_stock_error(self, title_text, message, color):
        """نافذة خطأ مخزون أثناء البيع"""
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=color, size=28),
                    ft.Text(title_text, color=color, weight="bold", size=16),
                ]
            ),
            content=ft.Container(
                content=ft.Text(message, size=14),
                padding=10,
            ),
            actions=[
                ft.ElevatedButton(
                    "حسناً",
                    bgcolor=color,
                    color="white",
                    on_click=lambda _: (setattr(dlg, 'open', False), self.page.update()),
                ),
            ],
            actions_alignment="center",
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _ask_debt_name(self, e):
        name_field = ft.TextField(label="اسم الزبون", autofocus=True)

        def on_confirm(ev):
            if name_field.value.strip():
                dlg.open = False
                self.page.update()
                self._complete_sale("debt", name_field.value.strip())

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("تسجيل دين"),
            content=ft.Column([ft.Text("أدخل اسم الزبون:"), name_field], tight=True),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: (setattr(dlg, 'open', False), self.page.update())),
                ft.ElevatedButton("تأكيد", on_click=on_confirm),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # =============================================
    #  صفحة إضافة منتج جديد
    # =============================================
    def show_inventory(self, e=None):
        self.current_page = "inventory"
        self.stop_camera()
        self.page.clean()

        name_in = ft.TextField(
            label="📦 اسم المنتج",
            hint_text="مثال: حليب طازج، أرز بسمتي...",
            border_radius=10,
            prefix_icon=ft.Icons.LABEL,
        )
        price_in = ft.TextField(
            label="💰 سعر البيع",
            hint_text="أدخل السعر بالأرقام فقط",
            keyboard_type="number",
            border_radius=10,
            prefix_icon=ft.Icons.ATTACH_MONEY,
        )
        barcode_in = ft.TextField(
            label="🔢 رقم الباركود",
            hint_text="أدخل الرقم يدوياً أو امسحه بالكاميرا ←",
            border_radius=10,
            expand=True,
            prefix_icon=ft.Icons.QR_CODE,
        )
        qty_in = ft.TextField(
            label="📊 الكمية المتوفرة",
            hint_text="عدد القطع في المخزون",
            keyboard_type="number",
            value="1",
            border_radius=10,
            prefix_icon=ft.Icons.NUMBERS,
        )

        def save(ev):
            if not name_in.value or not price_in.value or not barcode_in.value:
                self.show_message("⚠️ يرجى ملء جميع الحقول!", "red")
                return
            try:
                price = float(price_in.value)
                qty = int(qty_in.value)
            except ValueError:
                self.show_message("❌ السعر أو الكمية غير صحيح! أدخل أرقام فقط", "red")
                return

            ok = self.db.add_product(
                Product(name=name_in.value, price=price, barcode=barcode_in.value, quantity=qty)
            )
            if ok:
                self.show_message(f"✅ تم حفظ المنتج '{name_in.value}' بنجاح!", "#4CAF50")
                name_in.value = ""
                price_in.value = ""
                barcode_in.value = ""
                qty_in.value = "1"
                self.page.update()
            else:
                self.show_message("❌ خطأ: هذا الباركود مسجل مسبقاً!", "red")

        self.page.add(
            ft.AppBar(
                title=ft.Text("إضافة منتج جديد"),
                bgcolor="#FF9800",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_home, icon_color="white", tooltip="رجوع للقائمة الرئيسية"),
            ),
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.ADD_BOX, color="#FF9800", size=24),
                                ft.Text("بيانات المنتج الجديد", size=20, weight="bold"),
                            ],
                            spacing=8,
                        ),
                        ft.Text("املأ البيانات التالية لإضافة منتج جديد للمخزون:", size=13, color="#888"),
                        ft.Container(height=10),
                        # حقل الاسم مع تسمية
                        ft.Text("اسم المنتج:", size=13, weight="bold", color="#555"),
                        name_in,
                        ft.Container(height=8),
                        # حقل السعر مع تسمية
                        ft.Text("سعر البيع (بالريال):", size=13, weight="bold", color="#555"),
                        price_in,
                        ft.Container(height=8),
                        # حقل الباركود مع تسمية وزر كاميرا
                        ft.Text("رقم الباركود:", size=13, weight="bold", color="#555"),
                        ft.Row(
                            [
                                barcode_in,
                                ft.IconButton(
                                    ft.Icons.CAMERA_ALT,
                                    on_click=lambda _: self.start_camera(barcode_in),
                                    tooltip="📷 اضغط لمسح الباركود بالكاميرا",
                                    icon_color="#FF9800",
                                    icon_size=28,
                                ),
                            ]
                        ),
                        ft.Container(height=8),
                        # حقل الكمية مع تسمية
                        ft.Text("الكمية المتوفرة في المخزون:", size=13, weight="bold", color="#555"),
                        qty_in,
                        ft.Container(height=15),
                        ft.ElevatedButton(
                            "💾 حفظ المنتج في النظام",
                            icon=ft.Icons.SAVE,
                            bgcolor="#FF9800",
                            color="white",
                            height=55,
                            width=400,
                            on_click=save,
                            tooltip="اضغط لحفظ المنتج في قاعدة البيانات",
                        ),
                    ],
                    scroll="auto",
                ),
            ),
        )

    # =============================================
    #  صفحة إدارة جميع المنتجات
    # =============================================
    def show_products_list(self, e=None):
        self.page.clean()
        
        self.products_view = ft.ListView(expand=True, spacing=5, padding=10)
        self.all_products = self.db.get_all_products()

        search_input = ft.TextField(
            label="🔍 بحث في المنتجات للتعديل",
            hint_text="ابحث بالاسم أو الباركود...",
            prefix_icon=ft.Icons.SEARCH,
            on_change=self._filter_products_list,
            border_radius=12,
            filled=True,
        )

        self._render_products_list(self.all_products)

        self.page.add(
            ft.AppBar(
                title=ft.Text("إدارة المنتجات والمخزون"),
                bgcolor="#2196F3",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_home, icon_color="white"),
            ),
            ft.Container(
                padding=10,
                content=ft.Column(
                    [
                        search_input,
                        ft.Row(
                            [
                                ft.Text(f"إجمالي عدد المنتجات: {len(self.all_products)}", size=14, color="#888", weight="bold"),
                            ],
                            alignment="spaceBetween",
                        )
                    ]
                )
            ),
            ft.Container(content=self.products_view, expand=True),
        )

    def _filter_products_list(self, e):
        query = e.control.value.strip().lower()
        if not query:
            self._render_products_list(self.all_products)
            return

        query_words = query.split()
        matches = []
        for p in self.all_products:
            p_name_lower = p.name.lower()
            p_barcode = p.barcode.lower()
            match_found = all(word in p_name_lower for word in query_words) or query in p_barcode
            if match_found:
                matches.append(p)
                
        self._render_products_list(matches)

    def _render_products_list(self, products_to_render):
        self.products_view.controls.clear()
        
        for p in products_to_render:
            low_stock = p.quantity <= 3
            self.products_view.controls.append(
                ft.Container(
                    bgcolor="#FFF3E0" if low_stock else "white",
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, "#FFB74D" if low_stock else "#EEEEEE"),
                    content=ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text(p.name, weight="bold", size=16),
                                    ft.Text(f"باركود: {p.barcode}", size=12, color="#888"),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Column(
                                [
                                    ft.Text(f"{p.price} ج.س", weight="bold", color="#1565C0"),
                                    ft.Text(
                                        f"مخزون: {p.quantity}" + (" ⚠️" if low_stock else ""),
                                        size=12,
                                        color="red" if low_stock else "#4CAF50" if p.quantity > 5 else "#FF9800",
                                        weight="bold",
                                    ),
                                ],
                                horizontal_alignment="end",
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        ft.Icons.EDIT,
                                        icon_color="#FF9800",
                                        icon_size=20,
                                        on_click=lambda _, prod=p: self._show_edit_product_dialog(prod),
                                        tooltip="تعديل الصنف / إضافة مخزون",
                                    ),
                                    ft.IconButton(
                                        ft.Icons.DELETE,
                                        icon_color="#E53935",
                                        icon_size=20,
                                        on_click=lambda _, pid=p.id: self._delete_product(pid),
                                        tooltip="حذف نهائي",
                                    ),
                                ],
                                spacing=0,
                            ),
                        ]
                    ),
                )
            )

        if not products_to_render:
            self.products_view.controls.append(
                ft.Container(
                    content=ft.Text("لا توجد منتجات مطابقة", size=16, color="#999", text_align="center"),
                    padding=50,
                    alignment=ft.alignment.center,
                )
            )
            
        try:
            self.page.update()
        except:
            pass

    def _show_edit_product_dialog(self, product):
        name_in = ft.TextField(label="اسم المنتج", value=product.name)
        price_in = ft.TextField(label="السعر", value=str(product.price), keyboard_type="number")
        barcode_in = ft.TextField(label="الباركود (يمكن تعديله)", value=product.barcode, prefix_icon=ft.Icons.QR_CODE)
        qty_in = ft.TextField(label="الكمية المتوفرة (أضف أو عدل)", value=str(product.quantity), keyboard_type="number", prefix_icon=ft.Icons.NUMBERS)

        def save_edits(e):
            try:
                new_price = float(price_in.value)
                new_qty = int(qty_in.value)
            except ValueError:
                self.show_message("السعر والكمية يجب أن تكون أرقاماً صحيحة!", "red")
                return

            if not name_in.value or not barcode_in.value:
                self.show_message("اسم المنتج والباركود مطلوبان!", "red")
                return

            success = self.db.update_product(product.id, name_in.value, new_price, barcode_in.value, new_qty)
            if success:
                self.show_message("✅ تم حفظ تعديلات المنتج بنجاح!", "green")
                dlg.open = False
                self.page.update()
                self.show_products_list() # Re-render to update the list
            else:
                self.show_message("❌ خطأ: هذا الباركود مسجل لمنتج آخر!", "red")

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([ft.Icon(ft.Icons.EDIT, color="#FF9800"), ft.Text("تعديل تفاصيل الصنف")]),
            content=ft.Column(
                [name_in, price_in, barcode_in, qty_in, ft.Text("ملاحظة: يمكنك تعديل المخزون مباشرة من هنا عند إعادة التعبئة.", size=11, color="#888")],
                tight=True,
            ),
            actions=[
                ft.TextButton("إلغاء", on_click=lambda _: (setattr(dlg, 'open', False), self.page.update())),
                ft.ElevatedButton("حفظ التغييرات", on_click=save_edits, bgcolor="#4CAF50", color="white"),
            ],
            actions_alignment="center",
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # =============================================
    #  مركز التقارير والإدارة
    # =============================================
    def show_reports(self, e=None):
        """صفحة التقارير الرئيسية - مركز الإدارة"""
        self.page.clean()
        today = datetime.now().strftime("%Y-%m-%d")
        stats = self.db.get_daily_reports(today)
        count = self.db.get_total_items_sold(today)

        cash_today = sum(s[0] for s in stats if s[1] == "cash")
        debt_today = sum(s[0] for s in stats if s[1] == "debt")
        total_today = cash_today + debt_today

        total_unpaid = self.db.get_total_unpaid_debts()
        total_cash_all = self.db.get_total_cash()
        low_stock = self.db.get_low_stock_products()

        self.page.add(
            ft.AppBar(
                title=ft.Text("مركز الإدارة والتقارير"),
                bgcolor="#7B1FA2",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_home, icon_color="white"),
            ),
            ft.Container(
                expand=True,
                padding=15,
                content=ft.Column(
                    [
                        # ملخص اليوم
                        ft.Text("ملخص اليوم", size=20, weight="bold", color="#333"),
                        ft.Text(f"{today}", size=13, color="#999"),
                        ft.Container(height=10),
                        ft.Row(
                            [
                                self._mini_stat("مبيعات اليوم", f"{total_today:.0f}", "#E91E63"),
                                self._mini_stat("نقد اليوم", f"{cash_today:.0f}", "#4CAF50"),
                                self._mini_stat("ديون اليوم", f"{debt_today:.0f}", "#FF9800"),
                                self._mini_stat("عمليات", str(count), "#2196F3"),
                            ],
                            spacing=8,
                        ),
                        ft.Container(height=15),

                        # ملخص عام
                        ft.Text("الملخص العام", size=20, weight="bold", color="#333"),
                        ft.Container(height=8),
                        self._stat_card("إجمالي النقد المحصّل", f"{total_cash_all:.2f} ج.س", "#4CAF50", ft.Icons.ACCOUNT_BALANCE_WALLET),
                        self._stat_card("إجمالي الديون المتبقية", f"{total_unpaid:.2f} ج.س", "#E53935", ft.Icons.WARNING_AMBER),
                        self._stat_card("منتجات منخفضة المخزون", str(len(low_stock)), "#FF9800", ft.Icons.INVENTORY),

                        ft.Container(height=20),
                        ft.Divider(),
                        ft.Container(height=10),

                        # أزرار التنقل للأقسام الفرعية
                        ft.Text("أقسام الإدارة", size=20, weight="bold", color="#333"),
                        ft.Container(height=10),
                        self._report_nav_card("سجل الديون والمدينين", "عرض من يدين لك وتسجيل السداد", ft.Icons.PEOPLE, "#E53935", self.show_debts_page),
                        self._report_nav_card("سجل المبيعات", "جميع عمليات البيع اليومية", ft.Icons.RECEIPT_LONG, "#2196F3", self.show_sales_history),
                        self._report_nav_card("تنبيهات المخزون", "المنتجات التي أوشكت على النفاد", ft.Icons.NOTIFICATION_IMPORTANT, "#FF9800", self.show_stock_alerts),
                    ],
                    scroll="auto",
                ),
            ),
        )

    def _mini_stat(self, label, value, color):
        return ft.Container(
            expand=True,
            bgcolor="white",
            border_radius=12,
            padding=12,
            shadow=ft.BoxShadow(blur_radius=4, color="#10000000"),
            content=ft.Column(
                [
                    ft.Text(value, size=22, weight="bold", color=color, text_align="center"),
                    ft.Text(label, size=10, color="#888", text_align="center"),
                ],
                horizontal_alignment="center",
                spacing=4,
            ),
        )

    def _stat_card(self, label, value, color, icon):
        return ft.Container(
            padding=16,
            margin=ft.margin.only(bottom=8),
            bgcolor="white",
            border_radius=12,
            shadow=ft.BoxShadow(blur_radius=4, color="#10000000"),
            content=ft.Row(
                [
                    ft.Icon(icon, color=color, size=26),
                    ft.Container(width=10),
                    ft.Text(label, size=14),
                    ft.Container(expand=True),
                    ft.Text(value, size=18, weight="bold", color=color),
                ]
            ),
        )

    def _report_nav_card(self, title, subtitle, icon, color, on_click):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color="white", size=24),
                        bgcolor=color,
                        width=45,
                        height=45,
                        border_radius=12,
                        alignment=ft.alignment.center,
                    ),
                    ft.Container(width=12),
                    ft.Column(
                        [
                            ft.Text(title, size=16, weight="bold", color="#333"),
                            ft.Text(subtitle, size=12, color="#888"),
                        ],
                        spacing=2,
                        expand=True,
                    ),
                    ft.Icon(ft.Icons.CHEVRON_LEFT, color="#CCC", size=20),
                ]
            ),
            padding=15,
            margin=ft.margin.only(bottom=10),
            bgcolor="white",
            border_radius=12,
            shadow=ft.BoxShadow(blur_radius=4, color="#10000000"),
            on_click=on_click,
        )

    # =============================================
    #  صفحة سجل الديون والمدينين
    # =============================================
    def show_debts_page(self, e=None):
        self.page.clean()
        debtors = self.db.get_debts_by_customer()
        total_unpaid = self.db.get_total_unpaid_debts()
        total_paid = self.db.get_paid_debts_total()

        debts_view = ft.ListView(expand=True, spacing=8, padding=10)

        for customer_name, total_debt, num_transactions in debtors:
            debts_view.controls.append(
                ft.Container(
                    bgcolor="white",
                    padding=15,
                    border_radius=12,
                    border=ft.border.all(1, "#FFCDD2"),
                    shadow=ft.BoxShadow(blur_radius=3, color="#08000000"),
                    content=ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Icon(ft.Icons.PERSON, color="#E53935", size=24),
                                    ft.Container(width=8),
                                    ft.Column(
                                        [
                                            ft.Text(customer_name or "بدون اسم", size=17, weight="bold"),
                                            ft.Text(f"{num_transactions} عملية", size=12, color="#888"),
                                        ],
                                        spacing=2,
                                        expand=True,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(f"{total_debt:.2f}", size=20, weight="bold", color="#E53935"),
                                            ft.Text("ج.س", size=11, color="#888"),
                                        ],
                                        horizontal_alignment="end",
                                        spacing=0,
                                    ),
                                ]
                            ),
                            ft.Container(height=8),
                            ft.Row(
                                [
                                    ft.OutlinedButton(
                                        "عرض التفاصيل",
                                        icon=ft.Icons.LIST,
                                        on_click=lambda _, c=customer_name: self.show_customer_detail(c),
                                    ),
                                    ft.Container(expand=True),
                                    ft.ElevatedButton(
                                        "تسجيل سداد الكل",
                                        icon=ft.Icons.CHECK_CIRCLE,
                                        bgcolor="#4CAF50",
                                        color="white",
                                        on_click=lambda _, c=customer_name: self._pay_all_debts(c),
                                    ),
                                ]
                            ),
                        ]
                    ),
                )
            )

        if not debtors:
            debts_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE, color="#4CAF50", size=60),
                            ft.Container(height=10),
                            ft.Text("لا توجد ديون مسجلة!", size=18, color="#4CAF50", weight="bold"),
                        ],
                        horizontal_alignment="center",
                    ),
                    padding=50,
                    alignment=ft.alignment.center,
                )
            )

        self.page.add(
            ft.AppBar(
                title=ft.Text("سجل الديون"),
                bgcolor="#E53935",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_reports, icon_color="white"),
            ),
            # شريط الملخص
            ft.Container(
                padding=15,
                bgcolor="#FFEBEE",
                content=ft.Row(
                    [
                        ft.Column(
                            [ft.Text("ديون متبقية", size=12, color="#C62828"), ft.Text(f"{total_unpaid:.2f} ج.س", size=18, weight="bold", color="#E53935")],
                            horizontal_alignment="center",
                            expand=True,
                        ),
                        ft.VerticalDivider(width=1, color="#EF9A9A"),
                        ft.Column(
                            [ft.Text("ديون مسددة", size=12, color="#2E7D32"), ft.Text(f"{total_paid:.2f} ج.س", size=18, weight="bold", color="#4CAF50")],
                            horizontal_alignment="center",
                            expand=True,
                        ),
                    ]
                ),
            ),
            ft.Container(content=debts_view, expand=True),
        )

    def show_customer_detail(self, customer_name):
        """عرض تفاصيل ديون زبون محدد"""
        self.page.clean()
        debts = self.db.get_customer_debts_detail(customer_name)

        detail_view = ft.ListView(expand=True, spacing=5, padding=10)

        for sale_id, date, total in debts:
            detail_view.controls.append(
                ft.Container(
                    bgcolor="white",
                    padding=12,
                    border_radius=10,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.RECEIPT, color="#E53935", size=20),
                            ft.Container(width=8),
                            ft.Column(
                                [
                                    ft.Text(f"فاتورة رقم #{sale_id}", weight="bold"),
                                    ft.Text(f"التاريخ: {date}", size=12, color="#888"),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(f"{total:.2f} ج.س", weight="bold", color="#E53935", size=16),
                            ft.IconButton(
                                ft.Icons.CHECK_CIRCLE,
                                icon_color="#4CAF50",
                                tooltip="تسجيل سداد",
                                on_click=lambda _, sid=sale_id: self._pay_single_debt(sid, customer_name),
                            ),
                        ]
                    ),
                )
            )

        self.page.add(
            ft.AppBar(
                title=ft.Text(f"ديون: {customer_name}"),
                bgcolor="#E53935",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_debts_page, icon_color="white"),
            ),
            ft.Container(
                padding=15,
                bgcolor="#FFEBEE",
                content=ft.Text(f"إجمالي الديون: {sum(d[2] for d in debts):.2f} ج.س", size=18, weight="bold", color="#C62828"),
            ),
            ft.Container(content=detail_view, expand=True),
            ft.Container(
                padding=15,
                content=ft.ElevatedButton(
                    "سداد جميع الديون",
                    icon=ft.Icons.CHECK_CIRCLE,
                    bgcolor="#4CAF50",
                    color="white",
                    height=50,
                    width=400,
                    on_click=lambda _: self._pay_all_debts(customer_name),
                ),
            ),
        )

    def _pay_single_debt(self, sale_id, customer_name):
        self.db.mark_debt_paid(sale_id)
        self.show_message("تم تسجيل السداد", "#4CAF50")
        self.show_customer_detail(customer_name)

    def _pay_all_debts(self, customer_name):
        self.db.mark_customer_debts_paid(customer_name)
        self.show_message(f"تم سداد جميع ديون {customer_name}", "#4CAF50")
        self.show_debts_page()

    # =============================================
    #  صفحة سجل المبيعات
    # =============================================
    def show_sales_history(self, e=None):
        self.page.clean()
        today = datetime.now().strftime("%Y-%m-%d")
        sales = self.db.get_all_sales(today)

        sales_view = ft.ListView(expand=True, spacing=5, padding=10)

        for sale_id, date, total, sale_type, customer, paid in sales:
            is_debt = sale_type == "debt"
            is_paid = paid == 1

            type_text = "دين" if is_debt else "نقد"
            type_color = "#FF9800" if is_debt and not is_paid else "#4CAF50"
            type_icon = ft.Icons.PERSON if is_debt else ft.Icons.PAYMENTS

            status_text = ""
            if is_debt:
                status_text = " (مسدد ✓)" if is_paid else " (غير مسدد)"

            sales_view.controls.append(
                ft.Container(
                    bgcolor="white",
                    padding=12,
                    border_radius=10,
                    content=ft.Row(
                        [
                            ft.Icon(type_icon, color=type_color, size=22),
                            ft.Container(width=8),
                            ft.Column(
                                [
                                    ft.Text(f"عملية #{sale_id} - {type_text}{status_text}", weight="bold", size=14),
                                    ft.Text(
                                        f"{customer}" if customer else "نقدي",
                                        size=12,
                                        color="#888",
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(f"{total:.2f} ج.س", weight="bold", color=type_color, size=16),
                        ]
                    ),
                )
            )

        if not sales:
            sales_view.controls.append(
                ft.Container(
                    content=ft.Text("لا توجد مبيعات اليوم", size=16, color="#999"),
                    padding=50,
                    alignment=ft.alignment.center,
                )
            )

        self.page.add(
            ft.AppBar(
                title=ft.Text("مبيعات اليوم"),
                bgcolor="#2196F3",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_reports, icon_color="white"),
            ),
            ft.Container(
                padding=10,
                content=ft.Text(f"عدد العمليات: {len(sales)}", size=14, color="#888"),
            ),
            ft.Container(content=sales_view, expand=True),
        )

    # =============================================
    #  صفحة تنبيهات المخزون
    # =============================================
    def show_stock_alerts(self, e=None):
        self.page.clean()
        low_stock = self.db.get_low_stock_products(threshold=5)

        alerts_view = ft.ListView(expand=True, spacing=5, padding=10)

        for p in low_stock:
            urgency_color = "#E53935" if p.quantity <= 1 else "#FF9800" if p.quantity <= 3 else "#FFC107"
            alerts_view.controls.append(
                ft.Container(
                    bgcolor="white",
                    padding=12,
                    border_radius=10,
                    border=ft.border.all(1, urgency_color),
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(str(p.quantity), size=16, weight="bold", color="white", text_align="center"),
                                bgcolor=urgency_color,
                                width=40,
                                height=40,
                                border_radius=20,
                                alignment=ft.alignment.center,
                            ),
                            ft.Container(width=10),
                            ft.Column(
                                [
                                    ft.Text(p.name, weight="bold", size=15),
                                    ft.Text(f"باركود: {p.barcode}", size=12, color="#888"),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Text(
                                "نفد!" if p.quantity <= 0 else "منخفض جداً" if p.quantity <= 1 else "منخفض",
                                size=13,
                                weight="bold",
                                color=urgency_color,
                            ),
                        ]
                    ),
                )
            )

        if not low_stock:
            alerts_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.THUMB_UP, color="#4CAF50", size=60),
                            ft.Container(height=10),
                            ft.Text("المخزون بحالة ممتازة!", size=18, color="#4CAF50", weight="bold"),
                        ],
                        horizontal_alignment="center",
                    ),
                    padding=50,
                    alignment=ft.alignment.center,
                )
            )

        self.page.add(
            ft.AppBar(
                title=ft.Text("تنبيهات المخزون"),
                bgcolor="#FF9800",
                color="white",
                leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=self.show_reports, icon_color="white"),
            ),
            ft.Container(
                padding=10,
                content=ft.Text(f"منتجات تحت الحد الأدنى (5 قطع): {len(low_stock)}", size=14, color="#888"),
            ),
            ft.Container(content=alerts_view, expand=True),
        )


if __name__ == "__main__":
    ft.app(target=AppUI)

def main(page: ft.Page):
    AppUI(page)

ft.app(target=main)