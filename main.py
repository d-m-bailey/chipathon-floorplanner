import sys
from PySide6.QtWidgets import QApplication
from floorplanner.gui.main_window import MainWindow

if __name__ == '__main__':
    app=QApplication(sys.argv)
    app.setApplicationName('Chipathon 2026 Floorplanner')
    window=MainWindow(); window.show()
    sys.exit(app.exec())
