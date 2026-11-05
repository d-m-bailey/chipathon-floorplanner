import argparse
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from floorplanner.gui.main_window import MainWindow


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description='Chipathon 2026 interactive floorplanner')
    parser.add_argument('filename',nargs='?',help='Saved floorplan JSON to open at startup')
    return parser.parse_args(argv)


def main(argv=None):
    args=parse_args(argv)
    app=QApplication([sys.argv[0]])
    app.setApplicationName('Chipathon 2026 Floorplanner')
    window=MainWindow(); window.show()
    if args.filename:
        QTimer.singleShot(0,lambda:window.guarded(lambda:window.load_file(args.filename,record_history=False)))
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
