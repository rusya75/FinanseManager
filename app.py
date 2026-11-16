"""Графический интерфейс «Менеджера личных финансов» (tkinter)."""

import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import messagebox, ttk

from manager import FinanceManager
from models import ALL_CATEGORIES, TRANSACTION_TYPES, ValidationError
from storage import CsvStorage, StorageError

# ==============================
# НАСТРОЙКИ И ЦВЕТА
# ==============================

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "transactions.csv"
DEMO_FILE = BASE_DIR / "data" / "demo_transactions.csv"

BG_COLOR = "#111827"
PANEL_COLOR = "#1F2937"
CARD_COLOR = "#273449"
TEXT_COLOR = "#F9FAFB"
MUTED_COLOR = "#9CA3AF"
ACCENT_COLOR = "#10B981"
ACCENT_HOVER = "#059669"
BLUE_COLOR = "#60A5FA"
RED_COLOR = "#F87171"

SORT_OPTIONS = {
    "Дата: сначала новые": ("date", True),
    "Дата: сначала старые": ("date", False),
    "Сумма: по убыванию": ("amount", True),
    "Сумма: по возрастанию": ("amount", False),
}


def format_money(value):
    """12345.6 -> '12 345.60 сом'."""
    return "{:,.2f}".format(value).replace(",", " ") + " сом"


# ==============================
# ГЛАВНЫЙ КЛАСС ПРИЛОЖЕНИЯ
# ==============================

class FinanceApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Менеджер личных финансов")
        self.root.geometry("1100x720")
        self.root.minsize(950, 650)
        self.root.configure(bg=BG_COLOR)

        self.manager = FinanceManager(CsvStorage(DATA_FILE))

        # значения фильтров хранятся в приложении, чтобы не сбрасываться при смене вкладки
        self.search_var = tk.StringVar()
        self.type_filter_var = tk.StringVar(value="Все")
        self.category_filter_var = tk.StringVar(value="Все")
        self.sort_var = tk.StringVar(value=next(iter(SORT_OPTIONS)))
        self.operations_table = None
        self.count_label = None

        self.setup_styles()
        self.create_interface()
        self.load_data()
        self.show_home()

    # ---------- подготовка ----------

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background=PANEL_COLOR,
            foreground=TEXT_COLOR,
            fieldbackground=PANEL_COLOR,
            rowheight=32,
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background=CARD_COLOR,
            foreground=TEXT_COLOR,
            font=("Segoe UI", 10, "bold"),
            padding=8,
        )
        style.map("Treeview", background=[("selected", "#374151")])

    def load_data(self):
        try:
            skipped = self.manager.load()
        except StorageError as error:
            messagebox.showerror("Ошибка загрузки", str(error), parent=self.root)
            return
        if skipped:
            messagebox.showwarning(
                "Повреждённые данные",
                "Пропущено повреждённых строк в файле данных: {}.".format(skipped),
                parent=self.root,
            )

    def create_interface(self):
        sidebar = tk.Frame(self.root, bg=PANEL_COLOR, width=220)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        tk.Label(
            sidebar, text="MY FINANCE", bg=PANEL_COLOR, fg=ACCENT_COLOR,
            font=("Segoe UI", 17, "bold"),
        ).pack(pady=(30, 35))

        menu_items = [
            ("Главная", self.show_home),
            ("Операции", self.show_operations),
            ("Статистика", self.show_statistics),
            ("Настройки", self.show_settings),
        ]
        for title, command in menu_items:
            tk.Button(
                sidebar, text="   " + title, anchor="w", command=command,
                bg=PANEL_COLOR, fg=TEXT_COLOR,
                activebackground=CARD_COLOR, activeforeground=TEXT_COLOR,
                relief="flat", bd=0, font=("Segoe UI", 11),
                padx=20, pady=12, cursor="hand2",
            ).pack(fill="x", padx=10, pady=3)

        self.main = tk.Frame(self.root, bg=BG_COLOR)
        self.main.pack(side="left", fill="both", expand=True, padx=30, pady=25)

    def clear_main(self):
        self.operations_table = None
        self.count_label = None
        for widget in self.main.winfo_children():
            widget.destroy()

    # ---------- вспомогательные виджеты ----------

    def add_title(self, text, subtitle=None):
        tk.Label(
            self.main, text=text, bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 24, "bold"),
        ).pack(anchor="w")
        if subtitle:
            tk.Label(
                self.main, text=subtitle, bg=BG_COLOR, fg=MUTED_COLOR, font=("Segoe UI", 11),
            ).pack(anchor="w", pady=(5, 0))

    def make_button(self, parent, text, command, color=ACCENT_COLOR, hover=ACCENT_HOVER):
        return tk.Button(
            parent, text=text, command=command, bg=color, fg="#FFFFFF",
            activebackground=hover, activeforeground="#FFFFFF", relief="flat",
            font=("Segoe UI", 10, "bold"), padx=14, pady=8, cursor="hand2",
        )

    def make_summary_cards(self, parent):
        cards = tk.Frame(parent, bg=BG_COLOR)
        cards.pack(fill="x", pady=(20, 25))

        card_data = [
            ("ОБЩИЙ БАЛАНС", self.manager.balance(), ACCENT_COLOR),
            ("ДОХОДЫ", self.manager.total_income(), BLUE_COLOR),
            ("РАСХОДЫ", self.manager.total_expenses(), RED_COLOR),
        ]
        for title, amount, color in card_data:
            card = tk.Frame(cards, bg=CARD_COLOR, padx=15, pady=18)
            card.pack(side="left", fill="both", expand=True, padx=(0, 12))
            tk.Label(
                card, text=title, bg=CARD_COLOR, fg=MUTED_COLOR, font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w")
            tk.Label(
                card, text=format_money(amount), bg=CARD_COLOR, fg=color, font=("Segoe UI", 16, "bold"),
            ).pack(anchor="w", pady=(12, 0))

    def build_table(self, parent, height):
        frame = tk.Frame(parent, bg=BG_COLOR)
        frame.pack(fill="both", expand=True)

        columns = ("date", "type", "category", "amount", "description")
        headings = {
            "date": "Дата", "type": "Тип", "category": "Категория",
            "amount": "Сумма", "description": "Описание",
        }
        widths = {"date": 100, "type": 90, "category": 130, "amount": 140, "description": 260}

        table = ttk.Treeview(
            frame, columns=columns, show="headings", height=height, selectmode="browse",
        )
        for column in columns:
            table.heading(column, text=headings[column])
            table.column(column, width=widths[column], anchor="e" if column == "amount" else "w")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.tag_configure("income", foreground=ACCENT_COLOR)
        table.tag_configure("expense", foreground=RED_COLOR)

        table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return table

    def fill_table(self, table, transactions):
        table.delete(*table.get_children())
        for transaction in transactions:
            tag = "income" if transaction.TYPE == "Доход" else "expense"
            table.insert(
                "", "end", iid=str(transaction.transaction_id), tags=(tag,),
                values=(
                    transaction.date_text,
                    transaction.TYPE,
                    transaction.category,
                    format_money(transaction.amount),
                    transaction.description,
                ),
            )

    # ---------- страница «Главная» ----------

    def show_home(self):
        self.clear_main()
        self.add_title("Главная панель", "Обзор ваших финансов")
        self.make_summary_cards(self.main)

        tk.Label(
            self.main, text="Последние операции", bg=BG_COLOR, fg=TEXT_COLOR,
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        latest = self.manager.search()[:8]
        if not latest:
            tk.Label(
                self.main,
                text="Операций пока нет. Добавьте первую на вкладке «Операции».",
                bg=BG_COLOR, fg=MUTED_COLOR, font=("Segoe UI", 11),
            ).pack(anchor="w")
            return

        table = self.build_table(self.main, height=8)
        self.fill_table(table, latest)

    # ---------- страница «Операции» ----------

    def show_operations(self):
        self.clear_main()
        self.add_title("Доходы и расходы")

        # строка фильтров
        filters = tk.Frame(self.main, bg=BG_COLOR)
        filters.pack(fill="x", pady=(18, 10))

        tk.Label(filters, text="Поиск:", bg=BG_COLOR, fg=MUTED_COLOR).pack(side="left")
        search_entry = tk.Entry(
            filters, textvariable=self.search_var, bg=CARD_COLOR, fg=TEXT_COLOR,
            insertbackground=TEXT_COLOR, relief="flat", font=("Segoe UI", 11), width=20,
        )
        search_entry.pack(side="left", padx=(6, 14), ipady=5)
        search_entry.bind("<KeyRelease>", lambda event: self.refresh_operations())

        type_box = ttk.Combobox(
            filters, textvariable=self.type_filter_var, values=["Все"] + list(TRANSACTION_TYPES),
            state="readonly", width=9,
        )
        type_box.pack(side="left", padx=(0, 8))

        category_box = ttk.Combobox(
            filters, textvariable=self.category_filter_var, values=["Все"] + list(ALL_CATEGORIES),
            state="readonly", width=14,
        )
        category_box.pack(side="left", padx=(0, 8))

        sort_box = ttk.Combobox(
            filters, textvariable=self.sort_var, values=list(SORT_OPTIONS), state="readonly", width=22,
        )
        sort_box.pack(side="left", padx=(0, 8))

        for box in (type_box, category_box, sort_box):
            box.bind("<<ComboboxSelected>>", lambda event: self.refresh_operations())

        self.make_button(
            filters, "Сбросить", self.reset_filters, color=CARD_COLOR, hover="#374151",
        ).pack(side="left")

        # строка кнопок действий
        actions = tk.Frame(self.main, bg=BG_COLOR)
        actions.pack(fill="x", pady=(0, 12))
        self.make_button(actions, "+ Добавить", self.add_operation).pack(side="left", padx=(0, 8))
        self.make_button(
            actions, "Изменить", self.edit_selected, color="#3B82F6", hover="#2563EB",
        ).pack(side="left", padx=(0, 8))
        self.make_button(
            actions, "Удалить", self.delete_selected, color="#EF4444", hover="#DC2626",
        ).pack(side="left")
        self.count_label = tk.Label(actions, text="", bg=BG_COLOR, fg=MUTED_COLOR, font=("Segoe UI", 10))
        self.count_label.pack(side="right")

        self.operations_table = self.build_table(self.main, height=14)
        self.refresh_operations()

    def refresh_operations(self):
        """Перерисовывает таблицу с учётом поиска, фильтров и сортировки."""
        if self.operations_table is None:
            return
        type_name = self.type_filter_var.get()
        category = self.category_filter_var.get()
        sort_by, descending = SORT_OPTIONS[self.sort_var.get()]

        items = self.manager.search(
            type_name=None if type_name == "Все" else type_name,
            category=None if category == "Все" else category,
            query=self.search_var.get(),
            sort_by=sort_by,
            descending=descending,
        )
        self.fill_table(self.operations_table, items)
        self.count_label.config(
            text="Показано: {} из {}".format(len(items), self.manager.count())
        )

    def reset_filters(self):
        self.search_var.set("")
        self.type_filter_var.set("Все")
        self.category_filter_var.set("Все")
        self.sort_var.set(next(iter(SORT_OPTIONS)))
        self.refresh_operations()

    def get_selected_id(self):
        selection = self.operations_table.selection() if self.operations_table else ()
        if not selection:
            messagebox.showwarning("Нет выбора", "Сначала выберите операцию в таблице.", parent=self.root)
            return None
        return int(selection[0])

    def add_operation(self):
        self.open_operation_form()

    def edit_selected(self):
        transaction_id = self.get_selected_id()
        if transaction_id is None:
            return
        try:
            transaction = self.manager.get(transaction_id)
        except LookupError as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return
        self.open_operation_form(transaction)

    def delete_selected(self):
        transaction_id = self.get_selected_id()
        if transaction_id is None:
            return
        if not messagebox.askyesno("Удаление", "Удалить выбранную операцию?", parent=self.root):
            return
        try:
            self.manager.delete(transaction_id)
        except (LookupError, StorageError) as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return
        self.refresh_operations()

    # ---------- форма добавления / изменения ----------

    def open_operation_form(self, transaction=None):
        editing = transaction is not None

        window = tk.Toplevel(self.root)
        window.title("Изменить операцию" if editing else "Добавить операцию")
        window.geometry("420x600")
        window.resizable(False, False)
        window.configure(bg=BG_COLOR)
        window.transient(self.root)
        window.wait_visibility()
        window.grab_set()

        tk.Label(
            window, text="Изменение операции" if editing else "Новая операция",
            bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 20, "bold"),
        ).pack(pady=(20, 15))

        form = tk.Frame(window, bg=BG_COLOR)
        form.pack(fill="x", padx=30)

        def add_label(text):
            tk.Label(form, text=text, bg=BG_COLOR, fg=TEXT_COLOR).pack(anchor="w")

        def add_entry(initial):
            entry = tk.Entry(
                form, bg=CARD_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR,
                relief="flat", font=("Segoe UI", 11),
            )
            entry.insert(0, initial)
            entry.pack(fill="x", ipady=7, pady=(5, 12))
            return entry

        type_var = tk.StringVar(value=transaction.TYPE if editing else "Расход")
        category_var = tk.StringVar(value=transaction.category if editing else "")

        add_label("Тип операции")
        type_box = ttk.Combobox(
            form, textvariable=type_var, values=list(TRANSACTION_TYPES), state="readonly",
        )
        type_box.pack(fill="x", pady=(5, 12))

        add_label("Сумма (сом)")
        amount_entry = add_entry("{:.2f}".format(transaction.amount) if editing else "")

        add_label("Категория")
        category_box = ttk.Combobox(form, textvariable=category_var, state="readonly")
        category_box.pack(fill="x", pady=(5, 12))

        def update_categories(event=None):
            categories = list(TRANSACTION_TYPES[type_var.get()].CATEGORIES)
            category_box.configure(values=categories)
            if category_var.get() not in categories:
                category_var.set(categories[0])

        type_box.bind("<<ComboboxSelected>>", update_categories)
        update_categories()

        add_label("Описание")
        description_entry = add_entry(transaction.description if editing else "")

        add_label("Дата (ДД.ММ.ГГГГ)")
        date_entry = add_entry(transaction.date_text if editing else date.today().strftime("%d.%m.%Y"))

        def save_operation():
            values = (
                type_var.get(),
                amount_entry.get(),
                category_var.get(),
                description_entry.get(),
                date_entry.get(),
            )
            try:
                if editing:
                    self.manager.update(transaction.transaction_id, *values)
                else:
                    self.manager.add(*values)
            except ValidationError as error:
                messagebox.showerror("Ошибка ввода", str(error), parent=window)
                return
            except (LookupError, StorageError) as error:
                messagebox.showerror("Ошибка", str(error), parent=window)
                return

            window.destroy()
            self.refresh_operations()

        self.make_button(
            window, "Сохранить операцию", save_operation,
        ).pack(pady=10)

    # ---------- страница «Статистика» ----------

    def show_statistics(self):
        self.clear_main()
        self.add_title("Статистика", "Структура доходов и расходов")
        self.make_summary_cards(self.main)

        columns = tk.Frame(self.main, bg=BG_COLOR)
        columns.pack(fill="both", expand=True)
        columns.columnconfigure(0, weight=1, uniform="stat")
        columns.columnconfigure(1, weight=1, uniform="stat")

        self.draw_category_bars(columns, 0, "Расходы по категориям", "Расход", RED_COLOR)
        self.draw_category_bars(columns, 1, "Доходы по категориям", "Доход", ACCENT_COLOR)

    def draw_category_bars(self, parent, column, title, type_name, color):
        box = tk.Frame(parent, bg=BG_COLOR)
        box.grid(row=0, column=column, sticky="nsew", padx=(0, 20) if column == 0 else (0, 0))

        tk.Label(
            box, text=title, bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w", pady=(0, 12))

        data = self.manager.totals_by_category(type_name)
        if not data:
            tk.Label(
                box, text="Пока нет данных для анализа.", bg=BG_COLOR, fg=MUTED_COLOR,
            ).pack(anchor="w")
            return

        grand_total = sum(amount for _, amount in data)
        for category, amount in data:
            share = amount / grand_total

            row = tk.Frame(box, bg=BG_COLOR)
            row.pack(fill="x", pady=5)
            tk.Label(
                row, text=category, bg=BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 10),
            ).pack(side="left")
            tk.Label(
                row, text="{} ({:.0f}%)".format(format_money(amount), share * 100),
                bg=BG_COLOR, fg=MUTED_COLOR, font=("Segoe UI", 10),
            ).pack(side="right")

            track = tk.Frame(box, bg=CARD_COLOR, height=10)
            track.pack(fill="x")
            tk.Frame(track, bg=color).place(relx=0, rely=0, relwidth=share, relheight=1)

    # ---------- страница «Настройки» ----------

    def show_settings(self):
        self.clear_main()
        self.add_title("Настройки")

        info = (
            "Менеджер личных финансов, версия 2.0\n"
            "Валюта: кыргызский сом (сом)\n"
            "Операций в базе: {}\n"
            "Файл данных: {}"
        ).format(self.manager.count(), DATA_FILE)
        tk.Label(
            self.main, text=info, bg=BG_COLOR, fg=MUTED_COLOR, justify="left", font=("Segoe UI", 11),
        ).pack(anchor="w", pady=(15, 20))

        buttons = tk.Frame(self.main, bg=BG_COLOR)
        buttons.pack(anchor="w")
        self.make_button(
            buttons, "Загрузить демо-данные", self.load_demo_data, color="#3B82F6", hover="#2563EB",
        ).pack(side="left", padx=(0, 10))
        self.make_button(
            buttons, "Удалить все данные", self.clear_all_data, color="#EF4444", hover="#DC2626",
        ).pack(side="left")

    def load_demo_data(self):
        try:
            demo_items = CsvStorage(DEMO_FILE).load()
        except StorageError as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return
        if not demo_items:
            messagebox.showinfo("Демо-данные", "Файл демо-данных не найден или пуст.", parent=self.root)
            return
        if not messagebox.askyesno(
            "Демо-данные", "Текущие данные будут заменены демонстрационными. Продолжить?", parent=self.root,
        ):
            return
        try:
            self.manager.replace_all(demo_items)
        except StorageError as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return
        self.show_settings()

    def clear_all_data(self):
        if not messagebox.askyesno(
            "Удаление", "Удалить все операции без возможности восстановления?", parent=self.root,
        ):
            return
        try:
            self.manager.clear()
        except StorageError as error:
            messagebox.showerror("Ошибка", str(error), parent=self.root)
            return
        self.show_settings()
