"""Бизнес-логика приложения: учёт операций, поиск, сортировка, статистика.

Класс не зависит ни от интерфейса, ни от формата файла: он получает хранилище
(BaseStorage) при создании. Благодаря этому логику можно тестировать отдельно.
"""

from models import Expense, Income, create_transaction
from storage import StorageError  # noqa: F401  (реэкспорт для удобства импорта)


class FinanceManager:
    def __init__(self, storage):
        self._storage = storage
        self._transactions = []

    # ---------- служебные методы ----------

    @staticmethod
    def _fix_ids(transactions):
        """Гарантирует, что у всех операций есть уникальные идентификаторы."""
        used = set()
        next_id = max((t.transaction_id for t in transactions if t.transaction_id is not None), default=0) + 1
        for transaction in transactions:
            if transaction.transaction_id is None or transaction.transaction_id in used:
                transaction.transaction_id = next_id
                next_id += 1
            used.add(transaction.transaction_id)

    def _next_id(self):
        return max((t.transaction_id for t in self._transactions), default=0) + 1

    def _apply(self, new_list):
        """Сохраняет новый список; если запись не удалась - возвращает прежнее состояние."""
        old_list = self._transactions
        self._transactions = new_list
        try:
            self._storage.save(new_list)
        except StorageError:
            self._transactions = old_list
            raise

    # ---------- загрузка ----------

    def load(self):
        """Загружает данные из хранилища. Возвращает число пропущенных повреждённых строк."""
        transactions = self._storage.load()
        self._fix_ids(transactions)
        self._transactions = transactions
        return self._storage.skipped_rows

    @property
    def transactions(self):
        return list(self._transactions)

    def count(self):
        return len(self._transactions)

    # ---------- операции над данными ----------

    def get(self, transaction_id):
        for transaction in self._transactions:
            if transaction.transaction_id == transaction_id:
                return transaction
        raise LookupError("Операция с номером {} не найдена.".format(transaction_id))

    def add(self, type_name, amount, category, description="", operation_date=None):
        transaction = create_transaction(
            type_name, amount, category, description, operation_date, self._next_id()
        )
        self._apply(self._transactions + [transaction])
        return transaction

    def update(self, transaction_id, type_name, amount, category, description="", operation_date=None):
        self.get(transaction_id)  # выбросит LookupError, если записи нет
        updated = create_transaction(
            type_name, amount, category, description, operation_date, transaction_id
        )
        new_list = [updated if t.transaction_id == transaction_id else t for t in self._transactions]
        self._apply(new_list)
        return updated

    def delete(self, transaction_id):
        self.get(transaction_id)
        self._apply([t for t in self._transactions if t.transaction_id != transaction_id])

    def replace_all(self, transactions):
        new_list = list(transactions)
        self._fix_ids(new_list)
        self._apply(new_list)

    def clear(self):
        self._apply([])

    # ---------- поиск, фильтрация, сортировка ----------

    def search(self, type_name=None, category=None, query="", sort_by="date", descending=True):
        """Фильтрует по типу, категории и тексту (в описании и категории), затем сортирует."""
        query = (query or "").strip().lower()
        result = []
        for transaction in self._transactions:
            if type_name and transaction.TYPE != type_name:
                continue
            if category and transaction.category != category:
                continue
            if query and query not in (transaction.description + " " + transaction.category).lower():
                continue
            result.append(transaction)

        if sort_by == "amount":
            key = lambda t: (t.amount, t.transaction_id)
        elif sort_by == "category":
            key = lambda t: (t.category.lower(), t.transaction_id)
        else:
            key = lambda t: (t.operation_date, t.transaction_id)
        return sorted(result, key=key, reverse=descending)

    # ---------- статистика ----------

    def total(self, type_name):
        return round(sum(t.amount for t in self._transactions if t.TYPE == type_name), 2)

    def total_income(self):
        return self.total(Income.TYPE)

    def total_expenses(self):
        return self.total(Expense.TYPE)

    def balance(self):
        return round(sum(t.signed_amount for t in self._transactions), 2)

    def totals_by_category(self, type_name):
        """Список (категория, сумма), отсортированный по убыванию суммы."""
        sums = {}
        for transaction in self._transactions:
            if transaction.TYPE == type_name:
                sums[transaction.category] = sums.get(transaction.category, 0) + transaction.amount
        return sorted(((c, round(s, 2)) for c, s in sums.items()), key=lambda item: item[1], reverse=True)
