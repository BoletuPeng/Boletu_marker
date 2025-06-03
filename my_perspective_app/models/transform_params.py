# my_perspective_app/models/transform_params.py
import os
import re

class TransformParams:
    def __init__(self, coords=None):
        """
        coords 为一个长度为4的列表，内部元素是 (x, y) 的浮点坐标
        """
        if coords is None:
            # 默认值
            self.coords = [(0.001, 0.001), (0.999, 0.001), (0.999, 0.999), (0.001, 0.999)]
        else:
            self.coords = coords

    # ----------------------------------------------------------------------
    #    1) 从文本中解析 <coor>...</coor>  / 如果没有则用老式4段解析
    # ----------------------------------------------------------------------
    @staticmethod
    def load_from_file(txt_path):
        """
        优先从 <coor> ... </coor> 块中解析4个坐标；
        如果未找到该块，则尝试老式的 '\n\n' 分割方式；
        如果文件都不存在，则返回默认 coords。
        """
        if not os.path.exists(txt_path):
            # 文件不存在 => 返回默认
            return TransformParams()

        with open(txt_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1) 尝试解析 <coor> 块
        coords_from_coor = TransformParams._parse_coor_block(content)
        if coords_from_coor is not None:
            # 找到并成功解析 => 用该结果
            return TransformParams(coords_from_coor)

        # 2) 否则回退到老式逻辑
        coords_old = TransformParams._parse_old_format(content)
        return TransformParams(coords_old)

    @staticmethod
    def _parse_coor_block(full_text: str):
        """
        在 full_text 中查找 <coor>...</coor> 块，解析其中的4行 (x,y)。
        若未找到或解析失败 => 返回 None。
        """
        pattern = re.compile(r"<coor>\s*(.*?)\s*</coor>", re.DOTALL | re.IGNORECASE)
        match = pattern.search(full_text)
        if not match:
            return None

        block_str = match.group(1).strip()
        if not block_str:
            return None

        # 逐行拆分
        lines = block_str.splitlines()
        coords = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # e.g. "(0.25,0.25)"
            line = line.strip("()")
            if "," not in line:
                return None
            x_str, y_str = line.split(",", 1)
            coords.append((float(x_str.strip()), float(y_str.strip())))

        if len(coords) != 4:
            return None

        return coords

    @staticmethod
    def _parse_old_format(full_text: str):
        """
        老式解析：以'\n\n'分割，得到4段 "(x,y)"。
        若解析不够4段，可补默认，也可自定义。
        """
        content = full_text.strip()
        parts = content.split("\n\n")
        coords = []
        for part in parts:
            part = part.strip().strip("()")
            if not part:
                continue
            x_str, y_str = part.split(",", 1)
            coords.append((float(x_str.strip()), float(y_str.strip())))

        # 若不足4个 => 用默认补上
        if len(coords) < 4:
            default_rest = [(0.25,0.25), (0.75,0.25), (0.75,0.75), (0.25,0.75)]
            coords += default_rest[len(coords):]

        # 若多于4个 => 只取前4
        if len(coords) > 4:
            coords = coords[:4]

        return coords

    # ----------------------------------------------------------------------
    #    2) 保存时：把 4坐标写入 <coor>...\n</coor>，并保留文件其他部分
    # ----------------------------------------------------------------------
    @staticmethod
    def save_to_file(txt_path, coords):
        """
        写入时：
         - 若文件已存在，先读出其内容；
         - 去掉旧的 <coor>...</coor> 块，或去掉老式4段；(演示为只去除 <coor> 块)
         - 在文本中插入新的 <coor>...\n</coor> 块；
         - 写回文件。

        你也可选择在去掉 <coor> 块后，同时也把老式坐标文本(如果能精确识别)去掉。
        """
        # 1) 若文件不存在，就新建空串
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                old_text = f.read()
        else:
            old_text = ""

        # 2) 去掉 <coor>...</coor> 块
        pattern = re.compile(r"<coor>\s*.*?\s*</coor>", re.DOTALL | re.IGNORECASE)
        cleaned_text = pattern.sub("", old_text).strip()

        # （可选）若想一起去掉老式4个坐标段，也可以用更精确的方式处理

        # 3) 构造新的 <coor> 块
        lines = []
        for (x, y) in coords:
            lines.append(f"({x},{y})")
        block_content = "\n".join(lines)
        new_coor_block = f"<coor>\n{block_content}\n</coor>"

        # 4) 将新的 <coor> block 追加到 cleaned_text
        #    中间留两行空行（或自定义），再写回文件
        if cleaned_text:
            final_text = cleaned_text + "\n\n" + new_coor_block + "\n"
        else:
            final_text = new_coor_block + "\n"

        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(final_text)

    # ----------------------------------------------------------------------
    #    3) load_for_image：不变，只是内部改用新的 load_from_file
    # ----------------------------------------------------------------------
    @staticmethod
    def load_for_image(image_path):
        """
        优先加载同名 _verified.txt，再加载 .txt，都没有则返回默认值。
        """
        base, ext = os.path.splitext(image_path)
        verified_path = base + "_verified.txt"
        normal_path = base + ".txt"

        if os.path.exists(verified_path):
            return TransformParams.load_from_file(verified_path)
        elif os.path.exists(normal_path):
            return TransformParams.load_from_file(normal_path)
        else:
            return TransformParams()  # 默认
