# my_perspective_app/main.py
import sys
from PySide6.QtWidgets import QApplication
from app import MyPerspectiveApp

def main():
    app = QApplication(sys.argv)
    window = MyPerspectiveApp()
    window.show()
    sys.exit(app.exec())
    
if __name__ == "__main__":
    main()
 