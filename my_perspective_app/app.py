# my_perspective_app/app.py
from PySide6.QtWidgets import QMainWindow
from views.main_window import MainWindow
from controllers.main_controller import MainController

class MyPerspectiveApp(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.main_window = MainWindow()
        self.setCentralWidget(self.main_window)
        
        # 控制器：管理加载文件/文件夹及整个界面的交互
        self.controller = MainController(self.main_window)
        
        # 设置主窗口标题、尺寸等
        self.setWindowTitle("Perspective Parameter Editor")
        self.resize(1280, 720)
