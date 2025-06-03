# my_perspective_app/models/sam_marks_params.py
import os
import re

class SamMarksParams:
    """
    专门管理 'sam2分割' 或类似模式下的一系列标记点，
    并可将它们读写到 <mark> ... <\mark> 段落中。

    统一规定：
      - 内存中: List[ (x_float, y_float, label_str) ]
      - 文件中: 每行形如 "(0.3,0.4),pos"  => label 全当字符串处理
    """

    @staticmethod
    def load_marks_from_text(full_text: str):
        """
        在给定的文本中查找 <mark>...</mark> 之间的内容；
        若找到，则解析每一行 '(x,y),label' 形式（label一律当字符串）。

        返回 List[(x_float, y_float, label_str)].
        若没找到，则返回空列表 [].
        """
        # 用正则找出 <mark>...</mark> 内容
        pattern = re.compile(r"<mark>\s*(.*?)\s*<\\mark>", re.DOTALL)
        match = pattern.search(full_text)
        if not match:
            return []  # 没有 <mark> 块

        marks_str_block = match.group(1).strip()
        if not marks_str_block:
            return []  # 块是空的

        lines = marks_str_block.splitlines()
        results = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # 形如: (0.1,0.723),pos
            if not line.startswith("(") or ")" not in line:
                continue
            coords_part, label_str = line.rsplit(")", 1)  # 从右边切一次
            coords_part = coords_part.strip("(")
            label_str = label_str.strip().strip(",")  # label_str 全当字符串

            # 拆分 x,y
            x_str, y_str = coords_part.split(",", 1)
            x_val = float(x_str.strip())
            y_val = float(y_str.strip())
            label_val = label_str  # 不转 int，直接当字符串

            results.append( (x_val, y_val, label_val) )
        return results

    @staticmethod
    def embed_marks_in_text(orig_text: str, marks):
        """
        将 'marks'(List[(x,y,label)]) 写到 <mark>...</mark> 块中。

        - 如果原文本中已有 <mark>...</mark>，则先去掉，再写新的。
        - 若 marks 为空，也会写一个空的 <mark>\n\n<\mark>.
        """
        # 1) 去掉原本的 <mark>...<\mark>
        pattern = re.compile(r"<mark>\s*.*?\s*<\\mark>", re.DOTALL)
        cleaned_text = pattern.sub("", orig_text).strip()

        # 2) 构造新的 <mark> 块
        mark_lines = []
        for (x, y, label) in marks:
            mark_lines.append(f"({x},{y}),{label}")  # label是字符串，直接放上去

        if mark_lines:
            marks_block = "\n".join(mark_lines)
            new_section = f"<mark>\n{marks_block}\n<\\mark>"
        else:
            # 即使没有mark，也要输出空的 <mark>...</\mark>
            new_section = "<mark>\n\n<\\mark>"

        # 3) 追加到 cleaned_text
        if cleaned_text:
            final_text = cleaned_text + "\n\n" + new_section + "\n"
        else:
            final_text = new_section + "\n"

        return final_text

    @classmethod
    def load_for_image(cls, image_path):
        """
        简易入口：尝试读取 image_path 对应的 _verified.txt 或 .txt，
        找到 <mark>...\mark> 块 => 解析 => 返回 [(x,y,label), ...]。
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
            return []

        with open(txt_path, "r", encoding="utf-8") as f:
            full_text = f.read()

        return cls.load_marks_from_text(full_text)

    @classmethod
    def save_to_file(cls, txt_path: str, marks):
        """
        读取旧文本 => 去掉已有 <mark> 段 => 插入新的 <mark> 段 => 写回
        marks 为 List[(x,y,label)].
        """
        if os.path.exists(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                old_text = f.read()
        else:
            old_text = ""

        final_text = cls.embed_marks_in_text(old_text, marks)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(final_text)
