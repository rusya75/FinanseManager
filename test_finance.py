"""Автоматические тесты логики приложения (без графического интерфейса).

Запуск:  python -m unittest -v
"""

import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from manager import FinanceManager
from models import Expense, Income, Transaction, ValidationError
from storage import BaseStorage, CsvStorage, StorageError

DEMO_FILE = Path(__file__).resolve().parent / "data" / "demo_transactions.csv"


class FinanceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "data.csv"
        self.manager = FinanceManager(CsvStorage(self.path))
        self.manager.load()


class TestAddAndStatistics(FinanceTestCase):
    def test_add_income_and_expense_update_totals(self):
        self.manager.add("Доход", "15000", "Стипендия", "Стипендия")
        self.manager.add("Расход", "450,50", "Еда", "Обед")
        self.assertEqual(self.manager.total_income(), 15000.0)
        self.assertEqual(self.manager.total_expenses(), 450.5)
        self.assertEqual(self.manager.balance(), 14549.5)

    def test_signed_amount_polymorphism(self):
        self.assertEqual(Income(100, "Зарплата").signed_amount, 100)
        self.assertEqual(Expense(100, "Еда").signed_amount, -100)

    def test_base_class_cannot_be_created(self):
        with self.assertRaises(TypeError):
            Transaction(100, "Еда")

    def test_empty_description_gets_default(self):
        item = self.manager.add("Расход", "10", "Еда", "   ")
        self.assertEqual(item.description, "Без описания")

    def test_totals_by_category_sorted_desc(self):
        self.manager.add("Расход", "100", "Еда")
        self.manager.add("Расход", "900", "Покупки")
        self.manager.add("Расход", "300", "Еда")
        self.assertEqual(self.manager.totals_by_category("Расход"), [("Покупки", 900.0), ("Еда", 400.0)])

    def test_ids_stay_unique_after_delete(self):
        first = self.manager.add("Расход", "10", "Еда")
        second = self.manager.add("Расход", "20", "Еда")
        self.manager.delete(first.transaction_id)
        third = self.manager.add("Расход", "30", "Еда")
        self.assertNotEqual(second.transaction_id, third.transaction_id)


class TestValidation(FinanceTestCase):
    def test_invalid_amounts_rejected(self):
        for bad in ["abc", "", "   ", "0", "-5", "nan", "inf", "1e999", "0,001", "2000000000"]:
            with self.subTest(amount=bad):
                with self.assertRaises(ValidationError):
                    self.manager.add("Расход", bad, "Еда")
        self.assertEqual(self.manager.count(), 0)

    def test_category_must_match_type(self):
        with self.assertRaises(ValidationError):
            self.manager.add("Расход", "100", "Зарплата")
        with self.assertRaises(ValidationError):
            self.manager.add("Доход", "100", "Еда")

    def test_unknown_type_rejected(self):
        with self.assertRaises(ValidationError):
            self.manager.add("Перевод", "100", "Еда")

    def test_future_date_rejected(self):
        tomorrow = (date.today() + timedelta(days=1)).strftime("%d.%m.%Y")
        with self.assertRaises(ValidationError):
            self.manager.add("Расход", "100", "Еда", "", tomorrow)

    def test_bad_date_format_rejected(self):
        for bad in ["31.02.2026", "вчера", "", "2026/10/01"]:
            with self.subTest(date=bad):
                with self.assertRaises(ValidationError):
                    self.manager.add("Расход", "100", "Еда", "", bad)

    def test_too_long_description_rejected(self):
        with self.assertRaises(ValidationError):
            self.manager.add("Расход", "100", "Еда", "а" * 101)


class TestEditDeleteSearch(FinanceTestCase):
    def setUp(self):
        super().setUp()
        self.manager.add("Расход", "450", "Еда", "Обед в столовой", "01.10.2026")
        self.manager.add("Расход", "1200", "Транспорт", "Проездной", "03.10.2026")
        self.manager.add("Доход", "15000", "Стипендия", "Стипендия", "05.10.2026")

    def test_search_by_text_case_insensitive(self):
        found = self.manager.search(query="ОБЕД")
        self.assertEqual([t.description for t in found], ["Обед в столовой"])

    def test_search_nothing_found(self):
        self.assertEqual(self.manager.search(query="самолёт"), [])

    def test_filter_by_type_and_category(self):
        self.assertEqual(len(self.manager.search(type_name="Расход")), 2)
        self.assertEqual(len(self.manager.search(category="Стипендия")), 1)
        self.assertEqual(len(self.manager.search(type_name="Доход", category="Еда")), 0)

    def test_sorting(self):
        by_amount = self.manager.search(sort_by="amount", descending=True)
        self.assertEqual([t.amount for t in by_amount], [15000.0, 1200.0, 450.0])
        by_date = self.manager.search(sort_by="date", descending=False)
        self.assertEqual([t.date_text for t in by_date], ["01.10.2026", "03.10.2026", "05.10.2026"])

    def test_update_changes_record(self):
        target = self.manager.search(query="Проездной")[0]
        self.manager.update(target.transaction_id, "Расход", "1500", "Транспорт", "Проездной", "03.10.2026")
        self.assertEqual(self.manager.get(target.transaction_id).amount, 1500.0)
        self.assertEqual(self.manager.count(), 3)

    def test_update_can_change_type(self):
        target = self.manager.search(query="Обед")[0]
        self.manager.update(target.transaction_id, "Доход", "450", "Подарок", "Вернули долг", "01.10.2026")
        self.assertIsInstance(self.manager.get(target.transaction_id), Income)

    def test_failed_update_keeps_old_data(self):
        target = self.manager.search(query="Проездной")[0]
        with self.assertRaises(ValidationError):
            self.manager.update(target.transaction_id, "Расход", "-1", "Транспорт", "", "03.10.2026")
        self.assertEqual(self.manager.get(target.transaction_id).amount, 1200.0)

    def test_delete_and_delete_missing(self):
        target = self.manager.search(query="Обед")[0]
        self.manager.delete(target.transaction_id)
        self.assertEqual(self.manager.count(), 2)
        with self.assertRaises(LookupError):
            self.manager.delete(target.transaction_id)


class TestStorage(FinanceTestCase):
    def test_save_and_reload(self):
        self.manager.add("Доход", "32000", "Подработка", "Сайт", "12.10.2026")
        self.manager.add("Расход", "5400", "Покупки", "Клавиатура, чёрная", "18.10.2026")

        new_manager = FinanceManager(CsvStorage(self.path))
        skipped = new_manager.load()
        self.assertEqual(skipped, 0)
        self.assertEqual(new_manager.count(), 2)
        self.assertEqual(new_manager.balance(), 26600.0)
        self.assertEqual(new_manager.search(query="чёрная")[0].description, "Клавиатура, чёрная")

    def test_missing_file_gives_empty_list(self):
        self.assertEqual(self.manager.count(), 0)

    def test_corrupted_rows_are_skipped(self):
        self.path.write_text(
            "id,type,amount,category,description,date\n"
            "1,Расход,100.00,Еда,Нормальная строка,2026-10-01\n"
            "2,Расход,abc,Еда,Плохая сумма,2026-10-01\n"
            "3,Перевод,100.00,Еда,Плохой тип,2026-10-01\n"
            "4,Расход,100.00,Еда,Плохая дата,не-дата\n"
            "5,Расход\n",
            encoding="utf-8",
        )
        manager = FinanceManager(CsvStorage(self.path))
        skipped = manager.load()
        self.assertEqual(skipped, 4)
        self.assertEqual(manager.count(), 1)

    def test_duplicate_ids_are_repaired(self):
        self.path.write_text(
            "id,type,amount,category,description,date\n"
            "1,Расход,100.00,Еда,Первая,2026-10-01\n"
            "1,Расход,200.00,Еда,Вторая,2026-10-02\n",
            encoding="utf-8",
        )
        manager = FinanceManager(CsvStorage(self.path))
        manager.load()
        ids = [t.transaction_id for t in manager.transactions]
        self.assertEqual(len(set(ids)), 2)

    def test_save_error_rolls_back(self):
        class BrokenStorage(BaseStorage):
            def load(self):
                return []

            def save(self, transactions):
                raise StorageError("диск недоступен")

        manager = FinanceManager(BrokenStorage())
        manager.load()
        with self.assertRaises(StorageError):
            manager.add("Расход", "100", "Еда")
        self.assertEqual(manager.count(), 0)

    def test_demo_file_is_valid(self):
        storage = CsvStorage(DEMO_FILE)
        items = storage.load()
        self.assertEqual(storage.skipped_rows, 0)
        self.assertGreaterEqual(len(items), 20)

    def test_replace_all_and_clear(self):
        items = CsvStorage(DEMO_FILE).load()
        self.manager.replace_all(items)
        self.assertEqual(self.manager.count(), len(items))
        self.manager.clear()
        self.assertEqual(self.manager.count(), 0)
        self.assertEqual(FinanceManager(CsvStorage(self.path)).load(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
