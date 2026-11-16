"""Модели предметной области: финансовые операции.

Класс Transaction - базовый (абстрактный) класс операции.
Классы Income и Expense - наследники: у каждого свой тип, знак и список категорий.
Вся проверка данных выполняется здесь, в сеттерах (инкапсуляция).
"""

import math
from datetime import date, datetime

MAX_AMOUNT = 1_000_000_000
MAX_DESCRIPTION_LENGTH = 100
DISPLAY_DATE_FORMAT = "%d.%m.%Y"
STORAGE_DATE_FORMAT = "%Y-%m-%d"

INCOME_CATEGORIES = ("Зарплата", "Стипендия", "Подработка", "Подарок", "Другое")
EXPENSE_CATEGORIES = ("Еда", "Транспорт", "Учёба", "Развлечения", "Покупки", "Связь", "Другое")
ALL_CATEGORIES = tuple(dict.fromkeys(INCOME_CATEGORIES + EXPENSE_CATEGORIES))


class ValidationError(ValueError):
    """Ошибка некорректных данных, введённых пользователем или прочитанных из файла."""


class Transaction:
    """Базовый класс финансовой операции (напрямую не создаётся)."""

    TYPE = ""
    SIGN = 0
    CATEGORIES = ()

    def __init__(self, amount, category, description="", operation_date=None, transaction_id=None):
        if type(self) is Transaction:
            raise TypeError("Transaction - базовый класс, используйте Income или Expense.")
        self._transaction_id = None
        self.transaction_id = transaction_id
        self.amount = amount
        self.category = category
        self.description = description
        self.operation_date = operation_date

    # ---------- статические методы разбора данных ----------

    @staticmethod
    def parse_amount(value):
        """Преобразует ввод в сумму: допускает запятую, отсекает nan, inf, нули и минусы."""
        if isinstance(value, str):
            value = value.strip().replace(" ", "").replace(",", ".")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValidationError("Сумма должна быть числом.")
        if not math.isfinite(number):
            raise ValidationError("Сумма должна быть конечным числом.")
        number = round(number, 2)
        if number <= 0:
            raise ValidationError("Сумма должна быть больше нуля.")
        if number > MAX_AMOUNT:
            raise ValidationError("Сумма слишком большая (максимум {:,}).".format(MAX_AMOUNT).replace(",", " "))
        return number

    @staticmethod
    def parse_date(value):
        """Принимает date, None (сегодня) или строку ДД.ММ.ГГГГ / ГГГГ-ММ-ДД."""
        if value is None:
            return date.today()
        if isinstance(value, datetime):
            result = value.date()
        elif isinstance(value, date):
            result = value
        else:
            text = str(value).strip()
            result = None
            for pattern in (DISPLAY_DATE_FORMAT, STORAGE_DATE_FORMAT):
                try:
                    result = datetime.strptime(text, pattern).date()
                    break
                except ValueError:
                    continue
            if result is None:
                raise ValidationError("Дата должна быть в формате ДД.ММ.ГГГГ.")
        if result > date.today():
            raise ValidationError("Дата операции не может быть в будущем.")
        return result

    # ---------- свойства с проверкой ----------

    @property
    def transaction_id(self):
        return self._transaction_id

    @transaction_id.setter
    def transaction_id(self, value):
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise ValidationError("Идентификатор должен быть положительным целым числом.")
        self._transaction_id = value

    @property
    def amount(self):
        return self._amount

    @amount.setter
    def amount(self, value):
        self._amount = self.parse_amount(value)

    @property
    def category(self):
        return self._category

    @category.setter
    def category(self, value):
        value = (value or "").strip()
        if value not in self.CATEGORIES:
            raise ValidationError("Категория «{}» недоступна для типа «{}».".format(value, self.TYPE))
        self._category = value

    @property
    def description(self):
        return self._description

    @description.setter
    def description(self, value):
        value = (value or "").strip()
        if len(value) > MAX_DESCRIPTION_LENGTH:
            raise ValidationError("Описание не должно быть длиннее {} символов.".format(MAX_DESCRIPTION_LENGTH))
        self._description = value or "Без описания"

    @property
    def operation_date(self):
        return self._operation_date

    @operation_date.setter
    def operation_date(self, value):
        self._operation_date = self.parse_date(value)

    # ---------- поведение ----------

    @property
    def signed_amount(self):
        """Сумма со знаком: доход - положительная, расход - отрицательная (полиморфизм)."""
        return self.SIGN * self.amount

    @property
    def date_text(self):
        return self.operation_date.strftime(DISPLAY_DATE_FORMAT)

    def to_row(self):
        """Строка для записи в CSV."""
        return [
            self.transaction_id,
            self.TYPE,
            "{:.2f}".format(self.amount),
            self.category,
            self.description,
            self.operation_date.strftime(STORAGE_DATE_FORMAT),
        ]

    def __str__(self):
        return "{} | {} | {:.2f} | {} | {}".format(
            self.date_text, self.TYPE, self.amount, self.category, self.description
        )


class Income(Transaction):
    """Доход."""

    TYPE = "Доход"
    SIGN = 1
    CATEGORIES = INCOME_CATEGORIES


class Expense(Transaction):
    """Расход."""

    TYPE = "Расход"
    SIGN = -1
    CATEGORIES = EXPENSE_CATEGORIES


TRANSACTION_TYPES = {Income.TYPE: Income, Expense.TYPE: Expense}


def create_transaction(type_name, amount, category, description="", operation_date=None, transaction_id=None):
    """Фабрика: создаёт Income или Expense по названию типа."""
    try:
        transaction_class = TRANSACTION_TYPES[type_name]
    except KeyError:
        raise ValidationError("Неизвестный тип операции: «{}».".format(type_name))
    return transaction_class(amount, category, description, operation_date, transaction_id)


def transaction_from_row(row):
    """Создаёт операцию из словаря-строки CSV (ключи: id, type, amount, category, description, date)."""
    raw_id = (row["id"] or "").strip()
    return create_transaction(
        type_name=(row["type"] or "").strip(),
        amount=row["amount"],
        category=row["category"],
        description=row.get("description"),
        operation_date=row["date"] if row["date"] else "",
        transaction_id=int(raw_id) if raw_id else None,
    )
