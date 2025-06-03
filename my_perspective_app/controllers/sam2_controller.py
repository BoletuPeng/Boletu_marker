# my_perspective_app\controllers\sam2_controller.py
from PySide6.QtCore import QPoint, Qt

class Sam2Point:
    """
    用于表示一个点 (x_rel, y_rel)，及其 'pos'/'neg' 等标签。
    若是框的某个角，则 label 类似 '0_0' / '0_1'，代表第0号框的左上角/右下角。
    """
    def __init__(self, x_rel, y_rel, label):
        self.x_rel = x_rel
        self.y_rel = y_rel
        self.label = label  # 'pos', 'neg', or 'N_0'/'N_1' etc

class Sam2Controller:
    """
    专门管理SAM2标注的点/框。类似 shape_transform_controller.py 的角色。
    外部 (Sam2Overlay) 会在鼠标事件中调用本类的方法，来完成：
      - 创建正点/负点
      - 创建框(两个角点)
      - 拖动点/框角
      - 删除点/框
      - hit test, etc.
    """

    def __init__(self, image_item):
        self.image_item = image_item
        # 在 image_item 里，我们假设 sam2_marks 是 List[(x,y,label_str)] 或自定义对象
        # 这里为了方便，我们转换成 Sam2Point 列表
        self.points = []
        self._load_points_from_item()

        # 拖拽状态
        self.dragging_index = None  # 正在被拖拽的点索引
        self.drag_offset = (0.0, 0.0)  # 可选，用于拖拽时的相对偏移

    def set_image_item(self, image_item):
        self.image_item = image_item
        self.points = []
        self._load_points_from_item()
        self.dragging_index = None

    def _load_points_from_item(self):
        """
        从 image_item.sam2_marks (List[(x, y, label)]) 中加载到 self.points
        """
        if not self.image_item:
            return
        if not hasattr(self.image_item, "sam2_marks"):
            self.image_item.sam2_marks = []

        for (x, y, label) in self.image_item.sam2_marks:
            pt = Sam2Point(x, y, label)
            self.points.append(pt)

    def save_points_back_to_item(self):
        """
        将当前 self.points 写回 image_item.sam2_marks
        用于最终保存 -> PreviewController -> SamMarksParams.save_to_file(...)
        """
        if not self.image_item:
            return
        # 清空并重新存
        self.image_item.sam2_marks = []
        for p in self.points:
            self.image_item.sam2_marks.append((p.x_rel, p.y_rel, p.label))

    # --------------------------------------------------------------------
    #    创建操作：点 (pos/neg) 或 新框 (两个角)
    # --------------------------------------------------------------------
    def create_point(self, x_rel, y_rel, is_positive=True):
        label = "pos" if is_positive else "neg"
        self.points.append(Sam2Point(x_rel, y_rel, label))

    def create_box(self, x_rel, y_rel):
        """
        在 (x_rel, y_rel) 创建一个左上角点，另一个角点位于 (x_rel+delta, y_rel+delta)。
        用 box_idx 作为区分(例如 当前已有多少对box，就用下一个编号)
        """
        box_index = self._get_next_box_index()
        # 默认 40px => 需转成相对坐标，但这里简化处理(要知道图像像素 w,h)
        # 为演示，假设 40px 相对宽高 = 0.05(自行调大/调小)
        # 或者你在 overlay 里先算好 x_rel2, y_rel2
        delta_rel = 0.05
        x2_rel = x_rel + delta_rel
        y2_rel = y_rel + delta_rel

        # 存 label => f"{box_index}_0" 代表 左上; f"{box_index}_1" 代表 右下
        # 你也可以在 mouseMove 里动态判断哪个是 left_top
        pt1 = Sam2Point(x_rel, y_rel, f"{box_index}_0")
        pt2 = Sam2Point(x2_rel, y2_rel, f"{box_index}_1")

        self.points.append(pt1)
        self.points.append(pt2)

    def _get_next_box_index(self):
        """
        找到尚未使用的 box 索引. (简单做法：扫描 self.points.label, 取最大+1)
        """
        used_indices = set()
        for p in self.points:
            if "_" in p.label:
                # 说明是 boxX_Y
                box_str, corner_str = p.label.split("_")
                try:
                    idx = int(box_str)
                    used_indices.add(idx)
                except:
                    pass
        if not used_indices:
            return 0
        return max(used_indices) + 1

    # --------------------------------------------------------------------
    #    删除操作：删除点 or 删除整框
    # --------------------------------------------------------------------
    def delete_point(self, index):
        if 0 <= index < len(self.points):
            # 如果它是框的一端 => 需要删除另一端(同box)？
            label = self.points[index].label
            if "_" in label:
                # e.g. "0_0" => box 0, corner 0
                box_str, corner_str = label.split("_")
                # 找到对方 corner
                self._delete_box_partner(box_str)
            # 最后再删自己
            self.points.pop(index)

    def _delete_box_partner(self, box_str):
        """
        找到 label.startswith(f"{box_str}_") 的另外一个点, 一并删除
        """
        to_remove_indices = []
        for i, p in enumerate(self.points):
            if p.label.startswith(box_str + "_"):
                to_remove_indices.append(i)
        # 注意: 要从后往前 pop, 以免下标变动
        for i in reversed(to_remove_indices):
            self.points.pop(i)

    # --------------------------------------------------------------------
    #    拖拽 & hit-test
    # --------------------------------------------------------------------
    def hit_test_point(self, x_px, y_px, widget_width, widget_height, threshold_px=15):
        """
        遍历 self.points, 计算它在像素坐标下的位置，与 (x_px, y_px) 比较距离
        threshold_px=15 => 点的可点击范围
        若击中多点，只返回第一个(或你可以改成返回最上层)
        """
        for i, pt in enumerate(self.points):
            px = pt.x_rel * widget_width
            py = pt.y_rel * widget_height
            dist_sq = (x_px - px)**2 + (y_px - py)**2
            if dist_sq <= threshold_px**2:
                return i
        return None

    def start_drag(self, index):
        self.dragging_index = index

    def drag_move(self, x_rel, y_rel):
        """
        将 dragging_index 指向的点移动到 (x_rel, y_rel).
        """
        if self.dragging_index is None:
            return
        if 0 <= self.dragging_index < len(self.points):
            pt = self.points[self.dragging_index]
            pt.x_rel = x_rel
            pt.y_rel = y_rel

    def end_drag(self):
        """
        鼠标释放
        若拖动的是一个框角 => 重新检查它与对方 corner 的位置, 确保(左上,右下)正确
        """
        if self.dragging_index is not None and 0 <= self.dragging_index < len(self.points):
            pt = self.points[self.dragging_index]
            if "_" in pt.label:
                box_str, corner_str = pt.label.split("_")
                # corner_str in {"0","1"}
                # 重新排序
                self._reorder_box_corners(box_str)
        self.dragging_index = None

    def _reorder_box_corners(self, box_str):
        """
        给box_str对应的那对 corners，重新确定谁是(左上角) label = f"{box_index}_0"
        谁是(右下角) label = f"{box_index}_1"
        做法:
         - 找到这两个点 => (x1,y1),(x2,y2)
         - min_x,min_y = 左上; max_x,max_y = 右下
         - 更新点坐标和 label
        """
        corner_indices = []
        for i, p in enumerate(self.points):
            if p.label.startswith(box_str+"_"):
                corner_indices.append(i)
        if len(corner_indices) != 2:
            return  # 数据异常？

        # 取出这两个点
        i1, i2 = corner_indices
        p1 = self.points[i1]
        p2 = self.points[i2]
        # 先把 (x1,y1) / (x2,y2) 拿出来
        x1, y1 = p1.x_rel, p1.y_rel
        x2, y2 = p2.x_rel, p2.y_rel

        # 计算 min/max
        left_x  = min(x1, x2)
        right_x = max(x1, x2)
        top_y   = min(y1, y2)
        bot_y   = max(y1, y2)

        # 决定谁是 corner0(左上), 谁是 corner1(右下)
        # corner0 => (left_x, top_y), corner1 => (right_x, bot_y)
        if (p1.x_rel == left_x) and (p1.y_rel == top_y):
            # p1 仍是 _0
            p1.label = f"{box_str}_0"
            p1.x_rel, p1.y_rel = left_x, top_y

            p2.label = f"{box_str}_1"
            p2.x_rel, p2.y_rel = right_x, bot_y
        else:
            # p1 改为 _1, p2 改为 _0, 依此类推
            p1.x_rel, p1.y_rel = right_x, bot_y
            p1.label = f"{box_str}_1"

            p2.x_rel, p2.y_rel = left_x, top_y
            p2.label = f"{box_str}_0"

    # --------------------------------------------------------------------
    #    改变点正负性
    # --------------------------------------------------------------------
    def toggle_point_pos_neg(self, index):
        if 0 <= index < len(self.points):
            pt = self.points[index]
            if pt.label == "pos":
                pt.label = "neg"
            elif pt.label == "neg":
                pt.label = "pos"
            # 如果是框角则不处理