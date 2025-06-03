# my_perspective_app/views/preview_widget.py
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QHBoxLayout, QVBoxLayout
from PySide6.QtCore import Signal, Qt, QRect, QPointF
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor
from .thumbnail_bar import ThumbnailBar
from models.transform_params import TransformParams

class PreviewWidget(QWidget):
    request_previous = Signal()
    request_next = Signal()
    toggle_params_signal = Signal()
    params_changed_signal = Signal(list)  # [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
    save_verified_signal = Signal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # ========== 上方：图片大图展示区域 ==========
        self.image_label = QLabel("无图片")
        self.image_label.setAlignment(Qt.AlignCenter)
        
        # “上一张”、“下一张”可以用按钮或监听键盘事件，这里示例按钮
        self.btn_prev = QPushButton("上一张")
        self.btn_next = QPushButton("下一张")
        self.btn_toggle_params = QPushButton("加载透视变形参数")
        self.btn_save = QPushButton("储存人工校准坐标")
        self.btn_save.setEnabled(False)  # 初始灰色
        
        self.btn_prev.clicked.connect(self.request_previous)
        self.btn_next.clicked.connect(self.request_next)
        self.btn_toggle_params.clicked.connect(self.toggle_params_signal.emit)
        self.btn_save.clicked.connect(self._on_save_clicked)

        # ========== 下方：缩略图条 ==========
        self.thumbnail_bar = ThumbnailBar(self)

        # ========== 主布局 ==========
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # 中间区域：大图
        main_layout.addWidget(self.image_label, stretch=1)
        
        # 按钮区（水平）
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.btn_toggle_params)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)

        # 在底部加上缩略图横条
        main_layout.addWidget(self.thumbnail_bar, stretch=0)

        # 当前图片 & 当前透视参数
        self.current_pixmap = None
        self.transform_params = TransformParams()  # 默认
        self.params_overlay_visible = False
        
        # 记录交互用的坐标
        self.dragging_point_index = None
    
    def display_image(self, image_item, transform_params):
        from PySide6.QtGui import QImage
        
        self.current_pixmap = QPixmap(image_item.image_path)
        self.image_label.setPixmap(self.current_pixmap)
        
        if transform_params is None:
            transform_params = TransformParams()  # 默认
        
        self.transform_params = transform_params
        self.params_overlay_visible = False
        self.btn_toggle_params.setText("加载透视变形参数")
        self.update()  # 刷新绘图
    
    def set_params_overlay_visible(self, visible):
        self.params_overlay_visible = visible
        if visible:
            self.btn_toggle_params.setText("隐藏透视变形参数")
        else:
            self.btn_toggle_params.setText("加载透视变形参数")
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.current_pixmap:
            return
        
        if self.params_overlay_visible:
            painter = QPainter(self)
            # 根据 image_label 的绝对位置来绘制
            label_pos = self.image_label.mapTo(self, self.image_label.rect().topLeft())
            
            # 以图片在 label 中的显示大小来换算坐标
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.width(), 
                                                      self.image_label.height(),
                                                      Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation)
            
            # 计算坐标转换比率
            w_ratio = scaled_pixmap.width()
            h_ratio = scaled_pixmap.height()
            
            # 在 label 上绘制 1->2->3->4->1
            pen = QPen(QColor(255, 0, 0), 2)
            painter.setPen(pen)
            
            coords = self.transform_params.coords
            
            # 把相对坐标转成实际绘制坐标
            actual_points = []
            for (x, y) in coords:
                px = label_pos.x() + x * w_ratio
                py = label_pos.y() + y * h_ratio
                actual_points.append((px, py))
            
            # 画连线
            for i in range(4):
                p1 = actual_points[i]
                p2 = actual_points[(i+1) % 4]
                painter.drawLine(p1[0], p1[1], p2[0], p2[1])
            
            # 画十字准星
            cross_half_size = 5
            for i, (px, py) in enumerate(actual_points):
                painter.drawLine(px - cross_half_size, py, px + cross_half_size, py)
                painter.drawLine(px, py - cross_half_size, px, py + cross_half_size)
            
            painter.end()
    
    def mousePressEvent(self, event):
        if not self.params_overlay_visible or not self.current_pixmap:
            return super().mousePressEvent(event)
        
        if event.button() == Qt.LeftButton:
            # 判断是否点中了某个点
            clicked_index = self._hit_test_point(event.pos())
            if clicked_index is not None:
                self.dragging_point_index = clicked_index
    
    def mouseMoveEvent(self, event):
        if self.dragging_point_index is not None and self.params_overlay_visible:
            # 根据鼠标当前位置更新 transform_params 中对应的 (x,y) 相对坐标
            label_pos = self.image_label.mapTo(self, self.image_label.rect().topLeft())
            
            # 以图片在 label 中的显示大小来换算
            scaled_pixmap = self.current_pixmap.scaled(self.image_label.width(),
                                                      self.image_label.height(),
                                                      Qt.KeepAspectRatio,
                                                      Qt.SmoothTransformation)
            w_ratio = scaled_pixmap.width()
            h_ratio = scaled_pixmap.height()
            
            # 鼠标相对于图片左上角的偏移
            dx = event.pos().x() - label_pos.x()
            dy = event.pos().y() - label_pos.y()
            
            # 转换成 [0,1] 范围内
            x_rel = dx / w_ratio
            y_rel = dy / h_ratio
            
            # 限制在 0~1 范围内
            x_rel = min(max(x_rel, 0), 1)
            y_rel = min(max(y_rel, 0), 1)
            
            self.transform_params.coords[self.dragging_point_index] = (x_rel, y_rel)
            self.update()
            
            # 首次拖动后，触发让“储存人工校准坐标”可点击
            self.btn_save.setEnabled(True)
            
            # 给外界发送参数更新信号
            self.params_changed_signal.emit(self.transform_params.coords)
            
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragging_point_index = None
        super().mouseReleaseEvent(event)
    
    def _hit_test_point(self, mouse_pos, threshold=10):
        """
        检测鼠标点离哪一个顶点距离较近
        """
        label_pos = self.image_label.mapTo(self, self.image_label.rect().topLeft())
        scaled_pixmap = self.current_pixmap.scaled(self.image_label.width(),
                                                  self.image_label.height(),
                                                  Qt.KeepAspectRatio,
                                                  Qt.SmoothTransformation)
        w_ratio = scaled_pixmap.width()
        h_ratio = scaled_pixmap.height()
        
        coords = self.transform_params.coords
        for i, (x_rel, y_rel) in enumerate(coords):
            px = label_pos.x() + x_rel * w_ratio
            py = label_pos.y() + y_rel * h_ratio
            dist_sq = (mouse_pos.x() - px)**2 + (mouse_pos.y() - py)**2
            if dist_sq <= threshold**2:
                return i
        return None
    
    def _on_save_clicked(self):
        self.save_verified_signal.emit(self.transform_params.coords)
