# my_perspective_app/views/side_panel.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt, Signal  

class SidePanel(QWidget):
    # 当像素高度改变时往外发射信号
    canvas_height_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        self.label_color = QLabel("线条颜色（示例：R 分量）")
        self.slider_color = QSlider(Qt.Horizontal)
        self.slider_color.setRange(0, 255)
        self.slider_color.setValue(255)  # 红色
        
        self.label_thickness = QLabel("线条粗细")
        self.slider_thickness = QSlider(Qt.Horizontal)
        self.slider_thickness.setRange(1, 10)
        self.slider_thickness.setValue(2)

        # === 新增：画布目标像素高度 ===
        self.label_canvas_height = QLabel("画布高度(像素)")
        self.slider_canvas_height = QSlider(Qt.Horizontal)
        self.slider_canvas_height.setRange(500, 4000)  
        self.slider_canvas_height.setValue(1000)  # 可作为默认值

        # 监听滑动条数值变化 => 发射信号
        self.slider_canvas_height.valueChanged.connect(self._on_canvas_height_changed)

        layout.addWidget(self.label_color)
        layout.addWidget(self.slider_color)
        layout.addWidget(self.label_thickness)
        layout.addWidget(self.slider_thickness)


        layout.addWidget(self.label_canvas_height)
        layout.addWidget(self.slider_canvas_height)

        layout.addStretch()
        
        # 若要实时与 PreviewWidget 交互，可以在此处发信号或注入回调

    def _on_canvas_height_changed(self, new_val):
        # 往外发射：画布像素高度
        self.canvas_height_changed.emit(new_val)

    def set_canvas_height(self, val: int):
        """
        对外API, 让MainController可以直接设置滑动条的值
        """
        self.slider_canvas_height.setValue(val)

    def get_canvas_height(self) -> int:
        """
        对外API, 让MainController或其他组件获取当前滑动条值
        """
        return self.slider_canvas_height.value()
