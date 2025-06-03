# my_perspective_app/views/overlays/perspective_overlay.py

from PySide6.QtCore import QObject, Signal, QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QMenu

from controllers.shape_transform_controller import ShapeTransformController

class PerspectiveOverlay(QObject):
    """
    管理“透视变形”相关的绘制和鼠标交互。
    内部持有 shape_transform_controller, 用于角点/中点的链式移动逻辑。
    当用户释放鼠标后，如有坐标更新，会发射 overlay_params_changed_signal("perspective", coords_4)。
    """

    # 与 PreviewWidget 沟通的通用信号：overlay_params_changed_signal(overlay_type, data)
    overlay_params_changed_signal = Signal(str, object)

    def __init__(self, image_item):
        super().__init__()
        self.image_item = image_item
        self.shape_controller = ShapeTransformController(image_item)
        # 如果需要区分 userFixed / systemFixed 时立即刷新，可做 init
        # self.shape_controller.refresh_fixed_states()

    def set_image_item(self, image_item):
        """
        当 PreviewController 切换到某张图片时，可让 overlay 更新指向的 image_item。
        """
        self.image_item = image_item
        self.shape_controller.set_image_item(image_item)

    def paint_overlay(self, painter: QPainter, scaled_w: int, scaled_h: int):
        """
        在 PreviewLabel.paintEvent 的末尾被调用，用于画 corners/midpoints/连线。
        """
        if not self.image_item:
            return

        info = self.shape_controller.get_drawing_info(scaled_w, scaled_h)

        # 1) 画 edges
        pen_line = QPen(QColor(200, 60, 60), 2)
        painter.setPen(pen_line)
        for (x1, y1, x2, y2) in info["edges"]:
            painter.drawLine(x1, y1, x2, y2)

        # 2) 画 corners
        for corner in info["corners"]:
            px = corner.x_rel * scaled_w
            py = corner.y_rel * scaled_h
            cross_half = 6
            if corner.userFixed:
                color = QColor(40, 130, 255)
            elif corner.systemFixed:
                color = QColor(180, 180, 180)
            else:
                color = QColor(0, 220, 0)
            pen_corner = QPen(color, 2)
            painter.setPen(pen_corner)
            painter.drawLine(px - cross_half, py, px + cross_half, py)
            painter.drawLine(px, py - cross_half, px, py + cross_half)
            # 角点 label
            painter.drawText(px + 8, py - 8, str(corner.label))

        # 3) 画 midpoints
        for m in info["midpoints"]:
            mx = m.x_rel * scaled_w
            my = m.y_rel * scaled_h
            if m.userFixed:
                color = QColor(255, 120, 0)
            elif m.systemFixed:
                color = QColor(160, 160, 160)
            else:
                color = QColor(0, 200, 255)
            pen_mid = QPen(color, 2)
            painter.setPen(pen_mid)
            radius = 5
            painter.drawEllipse(mx - radius, my - radius, radius * 2, radius * 2)

    # --------------------- 鼠标事件 ---------------------

    def mouse_press_event(self, label_widget, event):
        """
        :param label_widget: PreviewLabel, 用于获取 size/坐标映射
        :param event: QMouseEvent
        """
        if event.button() == Qt.LeftButton:
            self.shape_controller.on_mouse_press(event.pos(), event.button(), label_widget.width(), label_widget.height())
        elif event.button() == Qt.RightButton:
            # 右键 => context menu
            context_menu_info = self.shape_controller.get_context_menu_info(event.pos(), label_widget.width(), label_widget.height())
            # 如果点中了 corner / midpoint，就显示菜单
            if context_menu_info:
                menu = QMenu(label_widget)
                for action_item in context_menu_info["actions"]:
                    # action_item 形如 ("固定(角点)", callback)
                    act = menu.addAction(action_item[0])
                chosen = menu.exec(label_widget.mapToGlobal(event.pos()))
                if chosen:
                    # 找到点击的那一项
                    for action_item in context_menu_info["actions"]:
                        if action_item[0] == chosen.text():
                            # 调用对应回调
                            action_item[1]()
                            label_widget.update()
                            return

    def mouse_move_event(self, label_widget, event):
        if event.buttons() & Qt.LeftButton:
            self.shape_controller.on_mouse_move(event.pos(), label_widget.width(), label_widget.height())
            label_widget.update()

    def mouse_release_event(self, label_widget, event):
        if event.button() == Qt.LeftButton:
            self.shape_controller.on_mouse_release(event.button())
            label_widget.update()
            # 释放后，如果有角点更新 => 发射 overlay_params_changed
            if self.shape_controller.image_item:
                coords_4 = self.shape_controller.image_item.get_coords_in_label_order()
                # 发射信号：("perspective", coords_4)
                self.overlay_params_changed_signal.emit("perspective", coords_4)
