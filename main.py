import os
os.environ.setdefault("QT_API", "pyside6")

import matplotlib
matplotlib.use("QtAgg")

import sys
from PySide6.QtWidgets import QApplication

from core.settings import Settings
from core.i18n import I18n
from core.history import History
from ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    base_path = os.path.dirname(os.path.abspath(__file__))

    settings = Settings(os.path.join(base_path, "config", "default_settings.json"))
    i18n = I18n(
        os.path.join(base_path, "config", "i18n"),
        settings.get("language", "zh_CN")
    )
    history = History()

    win = MainWindow(base_path, settings, i18n, history)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()