# my_perspective_app/views/thumbnail_bar.py

from PySide6.QtWidgets import QWidget, QLabel, QHBoxLayout, QVBoxLayout, QScrollArea, QMenu
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

class HorizontalScrollArea(QScrollArea):
    """
    专门用于 ThumbnailBar 的 QScrollArea，重写 wheelEvent 实现“水平滚动”。
    """
    def wheelEvent(self, event):
        """
        默认的 QScrollArea.wheelEvent 是垂直滚动，这里改成水平滚动。
        """
        # 如果需要兼容 Shift/Alt 等修饰键，也可进一步判断
        delta = event.angleDelta().y()  # 垂直滚轮量
        step = 40  # 一次滚动多少像素，可自行调大/调小
        bar = self.horizontalScrollBar()
        if delta > 0:
            # 滚轮向上 => 往左滚
            bar.setValue(bar.value() - step)
        else:
            # 滚轮向下 => 往右滚
            bar.setValue(bar.value() + step)

        event.accept()

class ThumbnailBar(QWidget):
    """
    一个横向滚动的缩略图条，用于展示若干图片的缩略图。
    - 点击某个缩略图会发射 thumbnail_clicked(index) 信号
    - 右键某个缩略图会弹出菜单，并可选择“移除”，从而发射 thumbnail_removed(index) 信号
    """
    thumbnail_clicked = Signal(int)    # 左键点击缩略图时，传递该缩略图的索引
    thumbnail_removed = Signal(int)    # 右键菜单选择“移除”时，传递该缩略图的索引

    def __init__(self, parent=None):
        super().__init__(parent)

        # 固定高度示例，可根据需求调节
        self.setFixedHeight(130)

        # 使用我们自定义的 HorizontalScrollArea
        self.scroll_area = HorizontalScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.h_layout = QHBoxLayout(self.container)
        self.h_layout.setContentsMargins(4, 4, 4, 4)
        self.h_layout.setSpacing(8)

        self.scroll_area.setWidget(self.container)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.scroll_area)
        self.setLayout(main_layout)

        # 维护所有的缩略图 Label
        self.thumbnail_labels = []
        # 当前选中索引，用于高亮
        self.selected_index = -1

    def clear_thumbnails(self):
        """
        清空原有缩略图（比如重新加载时需要先清空）
        """
        for lbl in self.thumbnail_labels:
            lbl.deleteLater()
        self.thumbnail_labels.clear()

    def set_thumbnails(self, image_paths):
        """
        传入一批图片路径，生成缩略图并加入到布局中。
        """
        # 先清空
        self.clear_thumbnails()

        for index, path in enumerate(image_paths):
            pixmap = QPixmap(path)
            # 缩放到固定大小（如100x100），可自行调整
            thumbnail_size = 100
            scaled_pix = pixmap.scaled(
                thumbnail_size, thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            lbl = _ClickableLabel(index)
            lbl.setPixmap(scaled_pix)
            lbl.setFixedSize(thumbnail_size, thumbnail_size)
            lbl.setStyleSheet("border: 2px solid transparent;")
            lbl.mouse_pressed.connect(self._on_label_left_clicked)
            lbl.right_clicked.connect(self._on_label_right_clicked)

            self.thumbnail_labels.append(lbl)
            self.h_layout.addWidget(lbl)

    def set_current_index(self, idx):
        """
        高亮当前索引的缩略图
        """
        self.selected_index = idx
        for i, lbl in enumerate(self.thumbnail_labels):
            if i == idx:
                lbl.setStyleSheet("border: 2px solid red;")
            else:
                lbl.setStyleSheet("border: 2px solid transparent;")

    def _on_label_left_clicked(self, index):
        self.thumbnail_clicked.emit(index)

    def _on_label_right_clicked(self, index):
        """
        右键点击缩略图 -> 弹出菜单
        """
        menu = QMenu(self)
        remove_action = menu.addAction("移除该图片")

        # 计算菜单出现的位置（需将缩略图局部坐标转换为全局）
        global_pos = self.mapToGlobal(self.thumbnail_labels[index].pos())
        chosen_action = menu.exec(global_pos)
        if chosen_action == remove_action:
            self.thumbnail_removed.emit(index)


class _ClickableLabel(QLabel):
    """
    可点击的 Label，根据鼠标事件发射信号。
    """
    mouse_pressed = Signal(int)
    right_clicked = Signal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mouse_pressed.emit(self.index)
        elif event.button() == Qt.RightButton:
            self.right_clicked.emit(self.index)
        super().mousePressEvent(event)