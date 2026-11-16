"""Хранение данных.

BaseStorage - абстрактный интерфейс хранилища (абстракция).
CsvStorage - реализация на CSV-файле. Менеджер работает только с интерфейсом BaseStorage,
поэтому CSV можно заменить на SQLite или JSON, не меняя остальной код.
"""

import csv
import os
from abc import ABC, abstractmethod
from pathlib import Path

from models import transaction_from_row


class StorageError(Exception):
    """Ошибка чтения или записи данных."""


class BaseStorage(ABC):
    def __init__(self):
        self.skipped_rows = 0  # сколько повреждённых строк пропущено при последней загрузке

    @abstractmethod
    def load(self):
        """Возвращает список операций."""

    @abstractmethod
    def save(self, transactions):
        """Сохраняет список операций."""


class CsvStorage(BaseStorage):
    FIELDS = ["id", "type", "amount", "category", "description", "date"]

    def __init__(self, path):
        super().__init__()
        self.path = Path(path)

    def load(self):
        self.skipped_rows = 0
        if not self.path.exists():
            return []

        transactions = []
        try:
            with open(self.path, newline="", encoding="utf-8-sig") as file:
                for row in csv.DictReader(file):
                    try:
                        transactions.append(transaction_from_row(row))
                    except (KeyError, TypeError, ValueError):
                        # ValidationError является подклассом ValueError
                        self.skipped_rows += 1
        except (OSError, UnicodeDecodeError, csv.Error) as error:
            raise StorageError("Не удалось прочитать файл {}: {}".format(self.path, error))
        return transactions

    def save(self, transactions):
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file)
                writer.writerow(self.FIELDS)
                for transaction in transactions:
                    writer.writerow(transaction.to_row())
            os.replace(temp_path, self.path)  # запись через временный файл защищает от потери данных
        except OSError as error:
            raise StorageError("Не удалось сохранить файл {}: {}".format(self.path, error))
