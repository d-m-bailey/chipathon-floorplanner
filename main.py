# Copyright 2026 D. Mitch Bailey
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

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
