# my_perspective_app/models/shape_transform.py

class CornerPoint:
    def __init__(self, x_rel, y_rel, label):
        self.x_rel = x_rel
        self.y_rel = y_rel
        self.label = label  # 1,2,3,4 (或更多)

        self.userFixed = False
        self.systemFixed = False

    @property
    def is_fixed(self):
        return self.userFixed or self.systemFixed


class MidPoint:
    def __init__(self, corner1_idx, corner2_idx):
        self.corner1_idx = corner1_idx
        self.corner2_idx = corner2_idx

        self.x_rel = 0.0
        self.y_rel = 0.0

        self.userFixed = False
        self.systemFixed = False

    @property
    def is_fixed(self):
        return self.userFixed or self.systemFixed


def update_system_fixed_states(corners, midpoints, max_iter=10):
    """
    迭代式地更新 corner / midpoint 的 systemFixed 状态。
    (示例规则与 demo 类似，可根据需求做更丰富的约束逻辑)
    """
    changed = True
    iteration = 0

    while changed and iteration < max_iter:
        changed = False
        iteration += 1

        # 更新角点
        for i, c in enumerate(corners):
            if c.userFixed:
                continue
            old_val = c.systemFixed
            new_val = False

            # 找它相连的 midpoints
            related_mids = []
            for m in midpoints:
                if m.corner1_idx == i or m.corner2_idx == i:
                    related_mids.append(m)

            for m in related_mids:
                if m.userFixed:
                    other_idx = m.corner2_idx if m.corner1_idx == i else m.corner1_idx
                    if corners[other_idx].is_fixed:
                        new_val = True
                        break

            if new_val != old_val:
                c.systemFixed = new_val
                changed = True

        # 更新中点
        for m in midpoints:
            if m.userFixed:
                continue
            old_val = m.systemFixed
            c1 = corners[m.corner1_idx]
            c2 = corners[m.corner2_idx]
            if c1.is_fixed and c2.is_fixed:
                new_val = True
            else:
                new_val = False

            if new_val != old_val:
                m.systemFixed = new_val
                changed = True


def recalc_midpoint_positions(corners, midpoints):
    """
    对未被用户固定的中点，重算位置 = (c1 + c2)/2
    """
    for m in midpoints:
        if m.userFixed:
            continue
        c1 = corners[m.corner1_idx]
        c2 = corners[m.corner2_idx]
        m.x_rel = (c1.x_rel + c2.x_rel) / 2.0
        m.y_rel = (c1.y_rel + c2.y_rel) / 2.0


def rebuild_midpoints_by_label_order(corners, midpoints):
    """
    根据 label 升序，重新定义 midpoints 的连线关系：
      0->1, 1->2, 2->3, 3->0 (假设只有4个角点)
    强制中点位置 = (corner1 + corner2)/2，忽略 userFixed
    然后再更新 systemFixed 状态
    """
    corners_sorted = sorted(corners, key=lambda c: c.label)

    # 找到原始索引
    def corner_original_index(corner_obj):
        return corners.index(corner_obj)

    sorted_indices = [corner_original_index(c) for c in corners_sorted]

    # 假设 midpoints 数量固定为4个
    # 如果以后要支持更多点，可在这里动态创建 midpoints
    midpoints[0].corner1_idx = sorted_indices[0]
    midpoints[0].corner2_idx = sorted_indices[1]
    midpoints[1].corner1_idx = sorted_indices[1]
    midpoints[1].corner2_idx = sorted_indices[2]
    midpoints[2].corner1_idx = sorted_indices[2]
    midpoints[2].corner2_idx = sorted_indices[3]
    midpoints[3].corner1_idx = sorted_indices[3]
    midpoints[3].corner2_idx = sorted_indices[0]

    # 强制中点坐标
    for m in midpoints:
        c1 = corners[m.corner1_idx]
        c2 = corners[m.corner2_idx]
        m.x_rel = (c1.x_rel + c2.x_rel) / 2.0
        m.y_rel = (c1.y_rel + c2.y_rel) / 2.0

    # 最后更新 systemFixed
    update_system_fixed_states(corners, midpoints)
