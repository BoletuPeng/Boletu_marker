# my_perspective_app/controllers/shape_transform_controller.py

from PySide6.QtWidgets import QMenu
from PySide6.QtCore import QPointF, Qt

from models.shape_transform import (
    update_system_fixed_states,
    recalc_midpoint_positions,
    rebuild_midpoints_by_label_order
)

class ShapeTransformController:
    """
    负责管理 PreviewLabel 上对 corner / midpoint 的鼠标交互 & 右键菜单等，完整移植了
    Demo 中的“链式带动”逻辑。
    
    当中点被固定 userFixed=True 后，拖动某端角点会撬动另一端角点，从而保持中点依旧不动。
    同理，若角点拖动时涉及到固定的中点/另一端角点，则进行递归带动或回退。
    """

    def __init__(self, image_item, label_widget):
        """
        :param image_item: 当前图对应的 ImageItem
        :param label_widget: PreviewLabel (用于 contextMenu / 触发 update)
        """
        self.image_item = image_item
        self.label_widget = label_widget

        # 当前是否在拖拽某个角点 / 中点
        self.dragging_corner_idx = None
        self.dragging_mid_idx = None

    # ============= 对外接口：切换当前 image_item =============
    def set_image_item(self, image_item):
        self.image_item = image_item
        self.dragging_corner_idx = None
        self.dragging_mid_idx = None

    # =========================================================
    #                鼠标事件总入口
    # =========================================================
    def on_mouse_press(self, pos, button):
        if button == Qt.LeftButton:
            # 左键 => 拖拽角点或中点
            c_idx = self.hit_test_corner(pos)
            if c_idx is not None:
                corner = self.image_item.corners[c_idx]
                # 若该 corner 未固定 => 准备拖动
                if not corner.is_fixed:
                    self.dragging_corner_idx = c_idx
                return

            m_idx = self.hit_test_midpoint(pos)
            if m_idx is not None:
                midpoint = self.image_item.midpoints[m_idx]
                # 若该 midpoint 未固定 => 准备拖动
                if not midpoint.is_fixed:
                    self.dragging_mid_idx = m_idx
                return

        elif button == Qt.RightButton:
            # 右键 => 弹出菜单(角点 / 中点)
            c_idx = self.hit_test_corner(pos)
            if c_idx is not None:
                self.show_corner_context_menu(c_idx, self.label_widget.mapToGlobal(pos))
                return

            m_idx = self.hit_test_midpoint(pos)
            if m_idx is not None:
                self.show_midpoint_context_menu(m_idx, self.label_widget.mapToGlobal(pos))
                return

    def on_mouse_move(self, pos):
        # 拖拽过程中 => 调用链式移动逻辑
        if self.dragging_corner_idx is not None:
            self._move_corner_by_mouse(self.dragging_corner_idx, pos)
            self.label_widget.update()
        elif self.dragging_mid_idx is not None:
            self._move_midpoint_by_mouse(self.dragging_mid_idx, pos)
            self.label_widget.update()

    def on_mouse_release(self, button):
        if button == Qt.LeftButton:
            # 拖拽结束 => 清空状态
            self.dragging_corner_idx = None
            self.dragging_mid_idx = None

            # 更新 systemFixed, 并重算所有未固定中点
            update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
            recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)
            self.label_widget.update()

    # =========================================================
    #          命中检测：hit_test_corner / hit_test_midpoint
    # =========================================================
    def hit_test_corner(self, mouse_pos, threshold=12):
        w = self.label_widget.width()
        h = self.label_widget.height()
        mx, my = mouse_pos.x(), mouse_pos.y()
        for i, c in enumerate(self.image_item.corners):
            px = c.x_rel * w
            py = c.y_rel * h
            dist_sq = (mx - px)**2 + (my - py)**2
            if dist_sq <= threshold**2:
                return i
        return None

    def hit_test_midpoint(self, mouse_pos, threshold=12):
        w = self.label_widget.width()
        h = self.label_widget.height()
        mx, my = mouse_pos.x(), mouse_pos.y()
        for i, m in enumerate(self.image_item.midpoints):
            px = m.x_rel * w
            py = m.y_rel * h
            dist_sq = (mx - px)**2 + (my - py)**2
            if dist_sq <= threshold**2:
                return i
        return None

    # =========================================================
    #      核心：拖拽移动 corner / midpoint + 链式带动
    # =========================================================

    def _move_corner_by_mouse(self, corner_idx, pos):
        """高层：当鼠标在移动某 corner 时调用，内部再用 _try_move_corner() 做递归带动"""
        w = self.label_widget.width()
        h = self.label_widget.height()

        new_x = max(0.0, min(1.0, pos.x() / w))
        new_y = max(0.0, min(1.0, pos.y() / h))

        # 调用递归函数进行带动；若返回 False => 移动失败，可做回退或忽略
        if not self._try_move_corner(corner_idx, new_x, new_y, visited=set()):
            pass

        # 每次成功移动后 => 重算中点位置(对未固定 midpoint)
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    def _move_midpoint_by_mouse(self, mid_idx, pos):
        """高层：当鼠标在移动某 midpoint 时调用，内部再用 _try_move_midpoint() 做递归带动"""
        w = self.label_widget.width()
        h = self.label_widget.height()

        new_mx = max(0.0, min(1.0, pos.x() / w))
        new_my = max(0.0, min(1.0, pos.y() / h))

        # 调用递归函数进行带动
        if not self._try_move_midpoint(mid_idx, new_mx, new_my, visited=set()):
            pass

        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    # ---------------------- 递归+回退：_try_move_corner ---------------------- #

    def _try_move_corner(self, corner_idx, new_x, new_y, visited):
        """
        核心链式逻辑：
        1) 若 corner 本身是固定 => 返回 False
        2) 否则先更新 corner.x_rel, corner.y_rel
        3) 找到所有与该 corner 相连的中点；若某中点 userFixed=True => 带动另一端 corner
           - 若另一端 corner 也固定 => 冲突 => 回退 => return False
           - 否则对另一端 corner 再次调用 _try_move_corner(...) 递归
        4) 若递归中返回False => 回退
        """
        corners = self.image_item.corners
        if corner_idx in visited:
            # 已访问 => 避免死循环
            return True

        corner = corners[corner_idx]
        if corner.is_fixed:
            return False

        visited.add(corner_idx)

        old_x, old_y = corner.x_rel, corner.y_rel
        corner.x_rel = new_x
        corner.y_rel = new_y

        # 找到与该 corner 相连的 midpoints
        related_mids = []
        for m in self.image_item.midpoints:
            if m.corner1_idx == corner_idx or m.corner2_idx == corner_idx:
                related_mids.append(m)

        # 若某个 mid 是 userFixed => 保持 mid 不变 => 带动另一端 corner
        for m in related_mids:
            if m.userFixed:
                # corner_idx => 另一端 => other_idx
                if m.corner1_idx == corner_idx:
                    other_idx = m.corner2_idx
                else:
                    other_idx = m.corner1_idx

                other_corner = corners[other_idx]
                if other_corner.is_fixed:
                    # 两端都固定 => 冲突 => 回退
                    corner.x_rel, corner.y_rel = old_x, old_y
                    return False
                else:
                    # 要使 m 不变 => other_corner = 2*m - corner
                    # clamp => [0..1], 可按需
                    target_x2 = 2*m.x_rel - corner.x_rel
                    target_y2 = 2*m.y_rel - corner.y_rel

                    # 递归带动 other_corner
                    if not self._try_move_corner(other_idx, target_x2, target_y2, visited):
                        corner.x_rel, corner.y_rel = old_x, old_y
                        return False

        return True

    # ---------------------- 递归+回退：_try_move_midpoint ---------------------- #

    def _try_move_midpoint(self, mid_idx, new_mx, new_my, visited):
        """
        当用户拖拽某 midpoint (且 midpoint 未固定) 时：
         1) 若 midpoint 本身是 fixed => 返回False (不允许拖动)
         2) 若两端 corner 都不固定 => 整条线平移
         3) 若一端固定、另一端不固定 => 用 _try_move_corner(...) 带动另一个 corner => 保持mid不变
         4) 若两端都固定 => 回退
        """
        midpoints = self.image_item.midpoints
        if mid_idx in visited:
            return True

        visited.add(mid_idx)

        m = midpoints[mid_idx]
        if m.is_fixed:
            # 不允许拖动
            return False

        old_mx, old_my = m.x_rel, m.y_rel
        m.x_rel = new_mx
        m.y_rel = new_my

        corners = self.image_item.corners
        c1_idx = m.corner1_idx
        c2_idx = m.corner2_idx
        c1 = corners[c1_idx]
        c2 = corners[c2_idx]

        both_not_fixed = (not c1.is_fixed) and (not c2.is_fixed)
        if both_not_fixed:
            # 整条线平移
            dx = new_mx - old_mx
            dy = new_my - old_my

            old_x1, old_y1 = c1.x_rel, c1.y_rel
            old_x2, old_y2 = c2.x_rel, c2.y_rel

            # 都能动 => 各移动 dx, dy
            c1.x_rel = max(0.0, min(1.0, c1.x_rel + dx))
            c1.y_rel = max(0.0, min(1.0, c1.y_rel + dy))
            c2.x_rel = max(0.0, min(1.0, c2.x_rel + dx))
            c2.y_rel = max(0.0, min(1.0, c2.y_rel + dy))

            # 若想严格处理中点固定 => 可能还需递归，但demo里一般只此一步
            # 这里暂不做进一步递归带动

        else:
            # 一端或两端固定
            if c1.is_fixed and c2.is_fixed:
                # 回退
                m.x_rel, m.y_rel = old_mx, old_my
                return False
            elif c1.is_fixed and not c2.is_fixed:
                # c2 跟随 => 计算 c2 新位置 = 2*mid - c1
                target_x2 = 2*new_mx - c1.x_rel
                target_y2 = 2*new_my - c1.y_rel

                if not self._try_move_corner(c2_idx, target_x2, target_y2, visited=set()):
                    m.x_rel, m.y_rel = old_mx, old_my
                    return False

            elif c2.is_fixed and not c1.is_fixed:
                target_x1 = 2*new_mx - c2.x_rel
                target_y1 = 2*new_my - c2.y_rel

                if not self._try_move_corner(c1_idx, target_x1, target_y1, visited=set()):
                    m.x_rel, m.y_rel = old_mx, old_my
                    return False

        return True

    # =========================================================
    #    右键菜单：固定/取消固定、改标号(交换 label) 等
    # =========================================================

    def show_corner_context_menu(self, corner_idx, global_pos):
        corner = self.image_item.corners[corner_idx]
        menu = QMenu(self.label_widget)

        if corner.userFixed:
            act_fix = menu.addAction("取消固定(角点)")
        else:
            act_fix = menu.addAction("固定(角点)")

        act_label = menu.addAction("更改标号")

        chosen = menu.exec(global_pos)
        if chosen is None:
            return

        if chosen == act_fix:
            corner.userFixed = not corner.userFixed
            update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
            self.label_widget.update()
        elif chosen == act_label:
            self.show_label_submenu(corner_idx, global_pos)

    def show_label_submenu(self, corner_idx, global_pos):
        menu = QMenu(self.label_widget)
        corner = self.image_item.corners[corner_idx]

        label_actions = []
        for lbl in [1, 2, 3, 4]:
            act = menu.addAction(f"改为 {lbl}")
            label_actions.append((act, lbl))

        chosen = menu.exec(global_pos)
        if chosen:
            for (act, lbl) in label_actions:
                if act == chosen:
                    old_label = corner.label
                    if old_label != lbl:
                        # 若其它角点有相同 label => 交换
                        for c in self.image_item.corners:
                            if c.label == lbl:
                                c.label = old_label
                                break
                        corner.label = lbl

                        # 物理排序 + 重建 midpoints
                        self._reorder_corners_by_label()
                        rebuild_midpoints_by_label_order(
                            self.image_item.corners,
                            self.image_item.midpoints
                        )

                        # 更新 systemFixed + 重算中点
                        update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
                        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

                    self.label_widget.update()
                    return

    def _reorder_corners_by_label(self):
        sorted_corners = sorted(self.image_item.corners, key=lambda c: c.label)
        self.image_item.corners = sorted_corners

    def show_midpoint_context_menu(self, mid_idx, global_pos):
        m = self.image_item.midpoints[mid_idx]
        menu = QMenu(self.label_widget)

        if m.userFixed:
            act_fix = menu.addAction("取消固定(中点)")
        else:
            act_fix = menu.addAction("固定(中点)")

        chosen = menu.exec(global_pos)
        if chosen == act_fix:
            m.userFixed = not m.userFixed
            update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
            self.label_widget.update()

    # =========================================================
    #         绘制信息提供 => 给 PreviewLabel paintEvent
    # =========================================================

    def get_drawing_info(self, w, h):
        """
        返回 corners, midpoints, edges(连线) 以给 PreviewLabel 的 paintEvent 绘制。
        """
        corners_sorted = sorted(self.image_item.corners, key=lambda c: c.label)
        edges = []
        # (1->2->3->4->1)
        for i in range(4):
            c1 = corners_sorted[i]
            c2 = corners_sorted[(i + 1) % 4]
            edges.append((
                c1.x_rel * w, c1.y_rel * h,
                c2.x_rel * w, c2.y_rel * h
            ))

        return {
            "corners": self.image_item.corners,
            "midpoints": self.image_item.midpoints,
            "edges": edges
        }
