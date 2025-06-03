# my_perspective_app/models/image_item.py
from .transform_params import TransformParams
from .shape_transform import CornerPoint, MidPoint, recalc_midpoint_positions, update_system_fixed_states
from PySide6.QtGui import QPixmap

class ImageItem:
    def __init__(self, image_path):
        self.image_path = image_path

        # sam2 mask 相关
        self.mask_pixmap = None    # QPixmap or None
        self.mask_visible = False  # 是否显示mask

        # 用来保存最新（在内存中）的 verified 坐标
        # 默认情况下是 None，表示还没加载过
        self.verified_coords = None  # 直接存4个点(备用)

        # 新增：shape_data 里存 corners / midpoints
        # 先初始化4 corner + 4 midpoint; 后面在加载图像时，会用实际文件中读到的 coords 来覆盖
        self.corners = [
            CornerPoint(0.25, 0.25, 1),
            CornerPoint(0.75, 0.25, 2),
            CornerPoint(0.75, 0.75, 3),
            CornerPoint(0.25, 0.75, 4),
        ]
        self.midpoints = [
            MidPoint(0, 1),
            MidPoint(1, 2),
            MidPoint(2, 3),
            MidPoint(3, 0),
        ]
        # 初始化一次 systemFixed
        recalc_midpoint_positions(self.corners, self.midpoints)
        update_system_fixed_states(self.corners, self.midpoints)

        self.sam2_marks = []

    def set_corners_from_coords(self, coords):
        """
        coords: [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]，顺序 = label 1,2,3,4
        """
        for i, (x, y) in enumerate(coords):
            corner = self.corners[i]
            corner.x_rel = x
            corner.y_rel = y
        recalc_midpoint_positions(self.corners, self.midpoints)
        update_system_fixed_states(self.corners, self.midpoints)

    def get_coords_in_label_order(self):
        """
        按 label 升序返回 4 个 (x,y)
        """
        corners_sorted = sorted(self.corners, key=lambda c: c.label)
        return [(c.x_rel, c.y_rel) for c in corners_sorted]