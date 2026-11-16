"""Точка входа: запуск приложения «Менеджер личных финансов»."""

import tkinter as tk

from app import FinanceApp


def main():
    root = tk.Tk()
    FinanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
