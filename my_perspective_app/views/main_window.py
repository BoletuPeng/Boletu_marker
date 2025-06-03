# my_perspective_app/views/main_window.py

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMenuBar
from PySide6.QtGui import QAction
from .preview_widget import PreviewWidget
from .side_panel import SidePanel
from .folder_selector import FolderSelector

class MainWindow(QWidget):
    """
    主窗口的内容部件(若你使用 QMainWindow，可以将它作为 centralWidget)。
    包含：
    - 菜单栏
    - 目标文件夹选择器(在菜单栏下方)
    - 左侧(或中间) PreviewWidget
    - 右侧 SidePanel
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        # 设置最小尺寸，避免过度挤压
        self.setMinimumSize(1000, 600)
        # 可选：如果你仍想在初始化时有个较大窗口，可用 resize，但别太大
        self.resize(1200, 800)

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # 菜单栏
        self.menu_bar = QMenuBar(self)
        file_menu = self.menu_bar.addMenu("文件")

        # 菜单动作
        self.action_load_file = QAction("加载文件", self)
        self.action_load_folder = QAction("加载整个文件夹", self)
        file_menu.addAction(self.action_load_file)
        file_menu.addAction(self.action_load_folder)

        file_menu.addSeparator()

        # 新增两个动作：保存到目标文件夹 + 强制同步目标文件夹
        self.action_save_to_folder = QAction("保存到目标文件夹", self)
        self.action_force_sync_folder = QAction("强制同步目标文件夹", self)
        file_menu.addAction(self.action_save_to_folder)
        file_menu.addAction(self.action_force_sync_folder)

        file_menu.addSeparator()

        # === 新增：加载配置文件 ===
        self.action_load_settings_file = QAction("加载配置文件", self)
        file_menu.addAction(self.action_load_settings_file)

        file_menu.addSeparator()

        # 关闭程序
        self.action_close_program = QAction("关闭程序", self)
        file_menu.addAction(self.action_close_program)
        # ============================

        # 将菜单栏加到布局
        main_layout.addWidget(self.menu_bar)

        # 目标文件夹选择器
        self.folder_selector = FolderSelector(self)
        main_layout.addWidget(self.folder_selector)

        # 主体区域：预览 + 侧边栏
        body_layout = QHBoxLayout()
        main_layout.addLayout(body_layout)

        self.preview_widget = PreviewWidget(self)
        self.side_panel = SidePanel(self)

        # 可选：给侧边栏设个固定宽度（示例 250）
        self.side_panel.setFixedWidth(250)

        body_layout.addWidget(self.preview_widget, stretch=3)
        body_layout.addWidget(self.side_panel, stretch=0)

        # 其他基本设置
        self.setWindowTitle("My Perspective App")
