# my_perspective_app/models/param_file_manager.py
import os
import re

from .transform_params import TransformParams
from .sam_marks_params import SamMarksParams

class ParamFileManager:
    """
    一个统一的管理器，用来在同一个 txt 文件里
    同时读写 `<coor>...</coor>` (4角点) + `<mark>...</mark>` (sam2点/框)。
    """

    @staticmethod
    def load_all(image_path):
        """
        读取 image_path 对应的 _verified.txt 或 .txt 文件，解析：
          - 4个透视角点 (coor)
          - sam2标记点 (mark)
        返回 (coords_list, marks_list)

        coords_list: [(x1,y1),(x2,y2),(x3,y3),(x4,y4)]
        marks_list : [ (x,y,label), ... ] (label可以是'pos','neg','0_0',...等)
        """
        base, _ = os.path.splitext(image_path)
        verified_path = base + "_verified.txt"
        normal_path = base + ".txt"

        txt_path = ""
        if os.path.exists(verified_path):
            txt_path = verified_path
        elif os.path.exists(normal_path):
            txt_path = normal_path
        else:
            # 文件都不存在 => 返回默认(4 corners) + 空mark
            return (TransformParams().coords, [])

        # 读取全文
        with open(txt_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        # (1) 提取 4 corners
        coords = ParamFileManager._parse_coor_block(full_text)
        if coords is None:
            # 如果没有 <coor>... => 再用 transform_params 旧逻辑试试
            # 也可以直接返回默认
            coords_obj = TransformParams.load_from_file(txt_path)
            coords = coords_obj.coords
        # (2) 提取 sam2 marks
        marks_obj = SamMarksParams.load_marks_from_text(full_text)
        marks = marks_obj

        return (coords, marks)

    @staticmethod
    def save_all(txt_path, coords, marks):
        """
        将 coords(4角点) 和 marks(sam2标记) 同时写入 txt_path：
          - 先读出旧文本
          - 去掉旧的 <coor>...</coor> 与 <mark>...</mark>
          - 在末尾插入新的 <coor> block + <mark> block
        """
        # 1) 若文件不存在，就建空串
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                old_text = f.read()
        else:
            old_text = ""

        # 2) 去掉 <coor>...</coor> 和 <mark>...</mark>
        coor_pattern = re.compile(r"<coor>\s*.*?</coor>", re.DOTALL | re.IGNORECASE)
        mark_pattern = re.compile(r"<mark>\s*.*?<\\mark>", re.DOTALL)
        cleaned = coor_pattern.sub("", old_text)
        cleaned = mark_pattern.sub("", cleaned)
        cleaned = cleaned.strip()

        # 3) 构造新的 <coor> 块
        coor_lines = []
        for (x,y) in coords:
            coor_lines.append(f"({x},{y})")
        coor_block = "<coor>\n" + "\n".join(coor_lines) + "\n</coor>"

        # 4) 构造新的 <mark> 块
        mark_lines = []
        for (x, y, label) in marks:
            mark_lines.append(f"({x},{y}),{label}")
        if mark_lines:
            mark_block = "<mark>\n" + "\n".join(mark_lines) + "\n<\\mark>"
        else:
            # 即使空，也可选择写空 <mark> ... <\mark>，看需求
            mark_block = "<mark>\n\n<\\mark>"

        # 5) 拼回
        final_text = cleaned
        if final_text:
            final_text += "\n\n" + coor_block + "\n\n" + mark_block + "\n"
        else:
            final_text = coor_block + "\n\n" + mark_block + "\n"

        # 6) 写回
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(final_text)

    # --------------------------------------------------------------------
    #   内部解析 <coor> block
    # --------------------------------------------------------------------
    @staticmethod
    def _parse_coor_block(full_text: str):
        """
        从全文中解析 <coor>...\n</coor> => 4行 (x,y)
        若没有找到或解析失败 => 返回 None
        """
        pattern = re.compile(r"<coor>\s*(.*?)\s*</coor>", re.DOTALL | re.IGNORECASE)
        match = pattern.search(full_text)
        if not match:
            return None
        block_str = match.group(1).strip()
        if not block_str:
            return None

        lines = block_str.splitlines()
        coords = []
        for line in lines:
            line = line.strip("() ")
            if not line:
                continue
            x_str, y_str = line.split(",", 1)
            coords.append( (float(x_str.strip()), float(y_str.strip())) )
        if len(coords) != 4:
            return None
        return coords
