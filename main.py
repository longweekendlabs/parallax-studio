import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app.ui.main_window import MainWindow
from app.ui.theme import QSS


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Parallax Studio")
    app.setOrganizationName("Long Weekend Labs")
    app.setStyle("Fusion")
    app.setStyleSheet(QSS)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
