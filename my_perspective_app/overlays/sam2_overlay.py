# my_perspective_app\overlays\sam2_overlay.py
from PySide6.QtCore import QObject, Signal, Qt, QPoint
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QMenu

from controllers.sam2_controller import Sam2Controller

class Sam2Overlay(QObject):
    """
    在 'sam2' 模式下的Overlay，负责在画面上绘制：
      - 正负点(圆点)
      - 框(两个角点 + 浅蓝色连线)
    并处理 右键创建/删除/改变标签, 左键拖动, etc.

    当用户对数据做任何修改(松开鼠标/删除/新增)时，就发射 overlay_params_changed_signal("sam2", data_list)。
    data_list 即 self.image_item.sam2_marks 的最新内容。
    """
    overlay_params_changed_signal = Signal(str, object)

    def __init__(self, image_item):
        super().__init__()
        self.image_item = image_item
        self.sam2_ctrl = Sam2Controller(image_item)

    def set_image_item(self, image_item):
        self.image_item = image_item
        self.sam2_ctrl.set_image_item(image_item)

    # -------------------------------------------------
    #  核心绘制
    # -------------------------------------------------
    def paint_overlay(self, painter: QPainter, scaled_w: int, scaled_h: int):
        if not self.image_item:
            return
        # （0） 若当前 image_item.mask_visible 且有 mask_pixmap，先绘制
        if self.image_item.mask_visible and self.image_item.mask_pixmap:
            # 将mask图缩放到 scaled_w, scaled_h
            scaled_mask = self.image_item.mask_pixmap.scaled(
                scaled_w, scaled_h,
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            # 在 (0,0) 绘制
            painter.drawPixmap(0, 0, scaled_mask)
        
        # （1）先绘制“占位mask” （若需要）
        # 例如画一个半透明灰色覆盖
        # painter.save()
        # painter.fillRect(0, 0, scaled_w, scaled_h, QColor(0,255,0,50))
        # painter.restore()
        # (若实际有mask图片，可 painter.drawPixmap(...))

        # （2）画点/框
        for pt in self.sam2_ctrl.points:
            # 先将相对坐标转换为像素
            x_px = pt.x_rel * scaled_w
            y_px = pt.y_rel * scaled_h

            if pt.label in ("pos", "neg"):
                # 这是一个“正负点”
                radius = 15  # 直径30px => 半径15
                color = QColor(0, 255, 0) if pt.label == "pos" else QColor(255, 0, 0)
                pen = QPen(color, 2)
                painter.setPen(pen)
                painter.drawEllipse(x_px - radius, y_px - radius, radius*2, radius*2)

            else:
                # 可能是 "0_0"/"0_1" => box
                # 我们先不直接画点，而是先收集2个角后画连线 => 见下文
                pass

        # 画框
        boxes = self._group_box_points()
        # boxes => { box_idx: ( (x0,y0), (x1,y1) ) }
        for box_idx, (corner0, corner1) in boxes.items():
            # corner0, corner1 是 Sam2Point
            x0_px = corner0.x_rel * scaled_w
            y0_px = corner0.y_rel * scaled_h
            x1_px = corner1.x_rel * scaled_w
            y1_px = corner1.y_rel * scaled_h

            # 浅蓝色边框
            pen_box = QPen(QColor(0,200,255), 2)
            painter.setPen(pen_box)
            painter.drawRect(min(x0_px, x1_px), min(y0_px, y1_px),
                             abs(x1_px - x0_px), abs(y1_px - y0_px))

            # 画两个角点(橙色)
            pen_corner = QPen(QColor(255,165,0), 2)  # 橙色
            painter.setPen(pen_corner)
            corner_radius = 6
            painter.drawEllipse(x0_px - corner_radius, y0_px - corner_radius, corner_radius*2, corner_radius*2)
            painter.drawEllipse(x1_px - corner_radius, y1_px - corner_radius, corner_radius*2, corner_radius*2)

    def _group_box_points(self):
        """
        将 label 类似 'X_0'/'X_1' 的点分组。
        返回 dict: { X: (pt0, pt1) }
        """
        boxes = {}
        for pt in self.sam2_ctrl.points:
            if "_" in pt.label:
                box_str, corner_str = pt.label.split("_")
                box_idx = int(box_str)
                if box_idx not in boxes:
                    boxes[box_idx] = [None, None]
                if corner_str == "0":
                    boxes[box_idx][0] = pt
                else:
                    boxes[box_idx][1] = pt
        # 转成 { box_idx: (pt0, pt1) }
        result = {}
        for k, pair in boxes.items():
            if pair[0] and pair[1]:
                result[k] = (pair[0], pair[1])
        return result

    # -------------------------------------------------
    #  鼠标事件
    # -------------------------------------------------
    def mouse_press_event(self, label_widget, event):
        if event.button() == Qt.RightButton:
            self._on_right_click(label_widget, event)
        elif event.button() == Qt.LeftButton:
            self._on_left_press(label_widget, event)

    def mouse_move_event(self, label_widget, event):
        if event.buttons() & Qt.LeftButton:
            self._on_left_drag(label_widget, event)

    def mouse_release_event(self, label_widget, event):
        if event.button() == Qt.LeftButton:
            self.sam2_ctrl.end_drag()
            # 拖拽结束 => 更新 item, 发射保存信号
            self.sam2_ctrl.save_points_back_to_item()
            self._emit_changed_signal()

        label_widget.update()

    def _on_left_press(self, label_widget, event):
        # 判断点击到哪个点
        w, h = label_widget.width(), label_widget.height()
        i = self.sam2_ctrl.hit_test_point(event.x(), event.y(), w, h, threshold_px=15)
        if i is not None:
            self.sam2_ctrl.start_drag(i)

    def _on_left_drag(self, label_widget, event):
        w, h = label_widget.width(), label_widget.height()
        x_rel = max(0, min(1, event.x() / w))
        y_rel = max(0, min(1, event.y() / h))
        self.sam2_ctrl.drag_move(x_rel, y_rel)
        label_widget.update()

    def _on_right_click(self, label_widget, event):
        """
        弹出菜单：若击中点/框角 => 显示“删除/改变正负性/删除框” 等
                否则 => 显示“创建点(正)/负/框”
        """
        w, h = label_widget.width(), label_widget.height()
        hit_index = self.sam2_ctrl.hit_test_point(event.x(), event.y(), w, h, threshold_px=15)

        menu = QMenu(label_widget)

        # 通用操作
        create_pos = menu.addAction("创建点(正)")
        create_neg = menu.addAction("创建点(负)")
        create_box = menu.addAction("创建框")

        if hit_index is not None:
            # 对已经存在的点 => “改变当前点正负性” + “删除当前点(或框)”
            pt = self.sam2_ctrl.points[hit_index]

            if pt.label in ("pos","neg"):
                # “改变当前点正负性” / “删除当前点”
                change_sign = menu.addAction("改变当前点正负性")
                delete_pt = menu.addAction("删除当前点")
            else:
                # 框的一端 => "删除当前框"
                delete_box = menu.addAction("删除当前框")

        chosen = menu.exec(label_widget.mapToGlobal(event.pos()))
        if not chosen:
            return  # 用户点到菜单外

        # 判断选了什么
        if chosen == create_pos:
            x_rel = event.x() / w
            y_rel = event.y() / h
            self.sam2_ctrl.create_point(x_rel, y_rel, is_positive=True)
            self._after_data_changed()
        elif chosen == create_neg:
            x_rel = event.x() / w
            y_rel = event.y() / h
            self.sam2_ctrl.create_point(x_rel, y_rel, is_positive=False)
            self._after_data_changed()
        elif chosen == create_box:
            x_rel = event.x() / w
            y_rel = event.y() / h
            self.sam2_ctrl.create_box(x_rel, y_rel)
            self._after_data_changed()

        elif hit_index is not None:
            pt = self.sam2_ctrl.points[hit_index]
            if pt.label in ("pos","neg"):
                # 可能点击了 改变当前点正负性 or 删除当前点
                if chosen.text() == "改变当前点正负性":
                    self.sam2_ctrl.toggle_point_pos_neg(hit_index)
                    self._after_data_changed()
                elif chosen.text() == "删除当前点":
                    self.sam2_ctrl.delete_point(hit_index)
                    self._after_data_changed()
            else:
                # "删除当前框"
                if chosen.text() == "删除当前框":
                    self.sam2_ctrl.delete_point(hit_index)
                    self._after_data_changed()

        label_widget.update()

    def _after_data_changed(self):
        """
        当用户新增/删除点(或框)后，立刻保存到 item 并发射事件
        """
        self.sam2_ctrl.save_points_back_to_item()
        self._emit_changed_signal()

    def _emit_changed_signal(self):
        """
        发射 overlay_params_changed_signal("sam2", data_list)
        data_list = [(x,y,label), ...]
        """
        if self.image_item:
            data = self.image_item.sam2_marks
            self.overlay_params_changed_signal.emit("sam2", data)
