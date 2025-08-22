import sys
from PyQt5.QtWidgets import QApplication
from function import GM8050ControlApp

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = GM8050ControlApp()
    window.show()
    sys.exit(app.exec_())