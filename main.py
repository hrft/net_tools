import sys
from PyQt5.QtWidgets import QApplication
from ui import VPNLauncher

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VPNLauncher()
    win.show()
    sys.exit(app.exec_())

