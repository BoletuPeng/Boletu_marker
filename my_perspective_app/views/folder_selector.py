# my_perspective_app/views/folder_selector.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton, QFileDialog
from PySide6.QtGui import QIcon
from PySide6.QtCore import Signal, Qt

class FolderSelector(QWidget):
    """
    显示目标文件夹图标 + 名字，当用户点击时可修改
    """
    folder_selected = Signal(str)  # 发出选定的文件夹路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self._target_folder = ""
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon("resources/icons/folder_icon.png").pixmap(24,24))
        
        self.name_label = QLabel("未选择")
        self.name_label.setStyleSheet("font-weight: bold;")
        
        self.btn_browse = QPushButton("更改目标文件夹")
        
        layout = QHBoxLayout()
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)
        layout.addWidget(self.name_label, 0, Qt.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self.btn_browse, 0, Qt.AlignVCenter)
        self.setLayout(layout)
        
        self.btn_browse.clicked.connect(self._on_browse_clicked)
    
    def _on_browse_clicked(self):
        folder_path = QFileDialog.getExistingDirectory(self, "选择目标文件夹")
        if folder_path:
            self._target_folder = folder_path
            self.name_label.setText(folder_path)
            self.folder_selected.emit(folder_path)
    
    def get_target_folder(self):
        return self._target_folder
