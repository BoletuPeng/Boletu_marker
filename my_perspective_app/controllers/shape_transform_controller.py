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
    原本负责管理 PreviewLabel 上对 corner / midpoint 的鼠标交互 & 右键菜单。
    现改为不直接操作 widget，而是由外部传入坐标和尺寸。
    """
    def __init__(self, image_item):
        """
        :param image_item: 当前图对应的 ImageItem
        :param label_widget: PreviewLabel (用于 contextMenu / 触发 update)
        """
        self.image_item = image_item

        # 拖拽中：
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

    def on_mouse_press(self, pos, button, widget_width, widget_height):
        """左键点击 corner/midpoint 准备拖拽；右键菜单则在 Overlay 里处理。"""
        if not self.image_item:
            return

        if button == Qt.LeftButton:
            c_idx = self.hit_test_corner(pos, widget_width, widget_height)
            if c_idx is not None:
                corner = self.image_item.corners[c_idx]
                # 若该 corner 未固定 => 准备拖动
                if not corner.is_fixed:
                    self.dragging_corner_idx = c_idx
                return

            m_idx = self.hit_test_midpoint(pos, widget_width, widget_height)
            if m_idx is not None:
                midpoint = self.image_item.midpoints[m_idx]
                # 若该 midpoint 未固定 => 准备拖动
                if not midpoint.is_fixed:
                    self.dragging_mid_idx = m_idx
                return

    def on_mouse_move(self, pos, widget_width, widget_height):
        if not self.image_item:
            return

        if self.dragging_corner_idx is not None:
            self._move_corner_by_mouse(self.dragging_corner_idx, pos, widget_width, widget_height)
        elif self.dragging_mid_idx is not None:
            self._move_midpoint_by_mouse(self.dragging_mid_idx, pos, widget_width, widget_height)

    def on_mouse_release(self, button):
        if not self.image_item:
            return

        if button == Qt.LeftButton:
            # 拖拽结束 => 清空状态
            self.dragging_corner_idx = None
            self.dragging_mid_idx = None
            # 更新 systemFixed
            update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
            recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    # ============= 右键菜单信息收集 =============
    def get_context_menu_info(self, pos, widget_width, widget_height):
        """
        返回一个 dict，包含：{ "actions": [(菜单文本, 回调函数), ...] }
        如果没点中 corner/midpoint，则返回 None
        """
        if not self.image_item:
            return None

        c_idx = self.hit_test_corner(pos, widget_width, widget_height)
        if c_idx is not None:
            return self._get_corner_context_menu_info(c_idx)
        m_idx = self.hit_test_midpoint(pos, widget_width, widget_height)
        if m_idx is not None:
            return self._get_midpoint_context_menu_info(m_idx)
        return None

    def _get_corner_context_menu_info(self, corner_idx):
        corner = self.image_item.corners[corner_idx]
        actions = []
        if corner.userFixed:
            actions.append(("取消固定(角点)", lambda: self._toggle_corner_fixed(corner_idx)))
        else:
            actions.append(("固定(角点)", lambda: self._toggle_corner_fixed(corner_idx)))

        # 更改标号子菜单 => 这里简化为4个
        for lbl in [1, 2, 3, 4]:
            actions.append((f"改为 {lbl}", lambda l=lbl: self._change_corner_label(corner_idx, l)))

        return {"actions": actions}

    def _get_midpoint_context_menu_info(self, mid_idx):
        m = self.image_item.midpoints[mid_idx]
        actions = []
        if m.userFixed:
            actions.append(("取消固定(中点)", lambda: self._toggle_midpoint_fixed(mid_idx)))
        else:
            actions.append(("固定(中点)", lambda: self._toggle_midpoint_fixed(mid_idx)))
        return {"actions": actions}

    def _toggle_corner_fixed(self, corner_idx):
        corner = self.image_item.corners[corner_idx]
        corner.userFixed = not corner.userFixed
        update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    def _toggle_midpoint_fixed(self, mid_idx):
        m = self.image_item.midpoints[mid_idx]
        m.userFixed = not m.userFixed
        update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    def _change_corner_label(self, corner_idx, new_label):
        corner = self.image_item.corners[corner_idx]
        old_label = corner.label
        if old_label == new_label:
            return
        # 若其它角点有相同 label => 交换
        for c in self.image_item.corners:
            if c.label == new_label:
                c.label = old_label
                break
        corner.label = new_label
        # 重新排序 + 重建
        self._reorder_corners_by_label()
        rebuild_midpoints_by_label_order(self.image_item.corners, self.image_item.midpoints)
        update_system_fixed_states(self.image_item.corners, self.image_item.midpoints)
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    def _reorder_corners_by_label(self):
        sorted_corners = sorted(self.image_item.corners, key=lambda c: c.label)
        self.image_item.corners = sorted_corners

    # ----------------------------------------------------------------
    #           核心：移动角点 / 中点（严格回退）
    # ----------------------------------------------------------------

    def _move_corner_by_mouse(self, corner_idx, pos, w, h):
        corner = self.image_item.corners[corner_idx]
        """
        1) 先记录 old_x, old_y
        2) 调用 _try_move_corner
        3) 若失败 => 还原 corner 坐标
        4) 再 recalc_midpoint_positions
        """
        old_x, old_y = corner.x_rel, corner.y_rel

        new_x = max(0.0, min(1.0, pos.x() / w))
        new_y = max(0.0, min(1.0, pos.y() / h))

        # 调用 _try_move_corner
        if not self._try_move_corner(corner_idx, new_x, new_y, visited=set()):
            # 回退
            corner.x_rel = old_x
            corner.y_rel = old_y

        # 成功或失败，都要重算一下未固定中点
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    def _move_midpoint_by_mouse(self, mid_idx, pos, w, h):
        """
        - 不先改 m.x_rel,m.y_rel，而是先验证 corner 是否能移动。
        - 只有全部成功后，才更新 mid.x_rel, mid.y_rel；
        - 如果任何一步失败 => 回退相关 corner => 不更新 mid。
        """
        m = self.image_item.midpoints[mid_idx]
        old_mx, old_my = m.x_rel, m.y_rel # 中点原坐标

        new_mx = max(0.0, min(1.0, pos.x() / w))
        new_my = max(0.0, min(1.0, pos.y() / h))


        c1_idx = m.corner1_idx
        c2_idx = m.corner2_idx
        c1 = self.image_item.corners[c1_idx]
        c2 = self.image_item.corners[c2_idx]

        # === Case 1: both_not_fixed ===
        if (not c1.is_fixed) and (not c2.is_fixed):
            dx = new_mx - old_mx
            dy = new_my - old_my

            # 记录角点的旧坐标
            old_x1, old_y1 = c1.x_rel, c1.y_rel
            # 尝试移动 corner1
            if not self._try_move_corner(c1_idx, old_x1 + dx, old_y1 + dy, visited=set()):
                # 失败 => 直接 return，不更新中点
                return

            old_x2, old_y2 = c2.x_rel, c2.y_rel
            # 再移动 corner2
            if not self._try_move_corner(c2_idx, old_x2 + dx, old_y2 + dy, visited=set()):
                # 回退 corner1
                self._try_move_corner(c1_idx, old_x1, old_y1, visited=set())
                return

            # 若都成功 => 最后再赋值中点
            m.x_rel = new_mx
            m.y_rel = new_my

        # === Case 2: 一端或两端固定 ===
        else:
            # 2) 一端固定 / 两端都固定
            if c1.is_fixed and c2.is_fixed:
                # 无法移动
                return
            elif c1.is_fixed and not c2.is_fixed:
                # 计算 c2 要移动到 (2*mid - c1)
                old_x2, old_y2 = c2.x_rel, c2.y_rel
                target_x2 = 2*new_mx - c1.x_rel
                target_y2 = 2*new_my - c1.y_rel

                if self._try_move_corner(c2_idx, target_x2, target_y2, visited=set()):
                    # 成功 => 更新 mid
                    m.x_rel = new_mx
                    m.y_rel = new_my
                else:
                    # 失败 => 不改 mid
                    return

            elif c2.is_fixed and not c1.is_fixed:
                old_x1, old_y1 = c1.x_rel, c1.y_rel
                target_x1 = 2*new_mx - c2.x_rel
                target_y1 = 2*new_my - c2.y_rel

                if self._try_move_corner(c1_idx, target_x1, target_y1, visited=set()):
                    m.x_rel = new_mx
                    m.y_rel = new_my
                else:
                    return

        # 最后再 recalc
        recalc_midpoint_positions(self.image_item.corners, self.image_item.midpoints)

    # ----------------------------------------------------------------
    #          核心递归函数：_try_move_corner
    # ----------------------------------------------------------------
    def _try_move_corner(self, corner_idx, new_x, new_y, visited):
        """
        - 若 corner 已固定 => return False
        - 若 visited => return True (防止死循环)
        - 否则先改 corner 坐标 => 对关联固定的 midpoint 做带动 => 若失败就回退
        - 去掉对 label_widget 的依赖
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

        # 查找跟它相连的 userFixed midpoint
        related_mids = []
        for m in self.image_item.midpoints:
            if m.corner1_idx == corner_idx or m.corner2_idx == corner_idx:
                related_mids.append(m)

        # 若某个 mid 是 userFixed => 保持 mid 不变 => 带动另一端 corner
        for m in related_mids:
            if m.userFixed:
                # 另一端 corner => other_idx
                if m.corner1_idx == corner_idx:
                    other_idx = m.corner2_idx
                else:
                    other_idx = m.corner1_idx

                other_corner = corners[other_idx]
                if other_corner.is_fixed:
                    # 两端都固定 => 回退
                    corner.x_rel = old_x
                    corner.y_rel = old_y
                    return False
                else:
                    # 要保持 mid 不变 => other_corner = 2*m - corner
                    target_x2 = 2*m.x_rel - corner.x_rel
                    target_y2 = 2*m.y_rel - corner.y_rel

                    # 递归带动另一 corner
                    if not self._try_move_corner(other_idx, target_x2, target_y2, visited):
                        corner.x_rel = old_x
                        corner.y_rel = old_y
                        return False

        return True

    # ----------------------------------------------------------------
    #           命中检测
    # ----------------------------------------------------------------
    def hit_test_corner(self, pos, widget_width, widget_height, threshold=12):
        if not self.image_item:
            return None

        mx, my = pos.x(), pos.y()

        for i, c in enumerate(self.image_item.corners):
            px, py = c.x_rel * widget_width, c.y_rel * widget_height
            dist_sq = (mx - px)**2 + (my - py)**2
            if dist_sq <= threshold**2:
                return i
        return None

    def hit_test_midpoint(self, pos, widget_width, widget_height, threshold=12):
        if not self.image_item:
            return None

        mx, my = pos.x(), pos.y()
        for i, m in enumerate(self.image_item.midpoints):
            px, py = m.x_rel * widget_width, m.y_rel * widget_height
            dist_sq = (mx - px)**2 + (my - py)**2
            if dist_sq <= threshold**2:
                return i
        return None

    # =========================================================
    #         绘制信息提供 => 给 PreviewLabel paintEvent
    # =========================================================

    def get_drawing_info(self, w, h):
        """
        返回 corners, midpoints, edges(连线)
        """
        if not self.image_item:
            return {"corners": [], "midpoints": [], "edges": []}

        corners_sorted = sorted(self.image_item.corners, key=lambda c: c.label)
        edges = []
        # 按 label 排序后 (1->2->3->4->1)
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
