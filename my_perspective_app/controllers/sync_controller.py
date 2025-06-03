# my_perspective_app/controllers/sync_controller.py

import os
import shutil
from PySide6.QtWidgets import QMessageBox, QInputDialog

from models.transform_params import TransformParams
from models.sam_marks_params import SamMarksParams

class SyncController:
    def __init__(self, parent):
        """
        parent: 可以是主窗口或一个能弹窗的 widget
        """
        self.parent = parent

    def force_sync_resources(self, resource_manager, target_folder):
        """
        '强制同步目标文件夹'：
          1) 清空 target_folder 内所有文件/子文件夹（请谨慎使用！）
          2) 再调用 sync_resources_in_pairs 做正常的同步复制
        """
        # 1) 清空 target_folder
        try:
            for item in os.listdir(target_folder):
                item_path = os.path.join(target_folder, item)
                item_path = os.path.normpath(item_path)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
        except Exception as e:
            QMessageBox.warning(self.parent, "错误", f"清空文件夹时出错：\n{str(e)}")
            return

        # 2) 再做“成对”同步
        self.sync_resources_in_pairs(resource_manager, target_folder)

    def sync_resources_in_pairs(self, resource_manager, target_folder):
        """
        逐个处理 ResourceManager 中的图片，以及它们的 .txt / _verified.txt 文件作为一个整体（pair）。
        如果有冲突（图片或任意txt同名），则询问用户处理方式：
          - 改名（对整个pair一起改）
          - 跳过（不复制这个pair）
          - 忽略后续（直接结束后续文件的复制）
        """
        images = resource_manager.get_all_images()
        if not images:
            return

        for image_item in images:
            src_image_path = image_item.image_path
            base_name = os.path.basename(src_image_path)  # e.g. "idcard01.jpg"
            name_no_ext, image_ext = os.path.splitext(base_name)

            # ====== 进入冲突检查 / 重命名循环 ======
            while True:
                # 1) 首先，我们在最终复制前，先把内存中的坐标/marks写入本地文件
                #    这样就能覆盖 cache/xxx_verified.txt 或 .txt 为新格式
                self._save_local_params_for_item(image_item)

                # 2) 根据最新的本地文件，收集 param_file_paths
                param_file_paths = []
                # .txt
                txt_path = os.path.normpath(os.path.splitext(src_image_path)[0] + ".txt")
                if os.path.exists(txt_path):
                    param_file_paths.append(txt_path)
                # _verified.txt
                verified_path = os.path.normpath(os.path.splitext(src_image_path)[0] + "_verified.txt")
                if os.path.exists(verified_path):
                    param_file_paths.append(verified_path)

            # === 执行复制前的冲突检查 ===
            # 只要其中任意文件在 target_folder 中已存在，就触发冲突对话框
                conflict_files = []
                # 先检查图片本身
                dst_image_name = name_no_ext + image_ext
                dst_image_path = os.path.normpath(os.path.join(target_folder, dst_image_name))

                if os.path.exists(dst_image_path):
                    conflict_files.append(dst_image_name)

                # 再检查参数文件
                # param_file_paths 可能有 0,1,2 个
                dst_param_pairs = []
                for param_src in param_file_paths:
                    _, param_ext = os.path.splitext(param_src)  # ".txt" or "_verified.txt"
                    dst_param_name = name_no_ext + param_ext
                    dst_param_path = os.path.normpath(os.path.join(target_folder, dst_param_name))
                    if os.path.exists(dst_param_path):
                        conflict_files.append(dst_param_name)
                    dst_param_pairs.append((param_src, dst_param_path))

                if conflict_files:
                    # === 有冲突，弹窗询问 ===
                    user_choice = self._ask_conflict_resolution(", ".join(conflict_files))
                    if user_choice == "skip":
                        break  # 跳过此pair，处理下一个
                    elif user_choice == "ignore":
                        return  # 直接结束整体复制
                    elif user_choice == "rename":
                        # 用户想改名 => 弹框让用户输入新的“基础名字”（不含扩展名）
                        new_base = self._ask_new_basename(name_no_ext)
                        if not new_base:
                            # 用户点取消 => 当做 skip 处理
                            break
                        # 替换 name_no_ext
                        name_no_ext = new_base
                        # 继续 while True，重新检查冲突
                        continue
                else:
                    # 无冲突 => 可以直接复制
                    try:
                        shutil.copy2(src_image_path, dst_image_path)
                        for param_src, dst_param_path in dst_param_pairs:
                            shutil.copy2(param_src, dst_param_path)
                    except Exception as e:
                        QMessageBox.warning(
                            self.parent, "错误",
                            f"复制文件时出错：\n{src_image_path} => {dst_image_path}\n\n{str(e)}"
                        )
                    break  # 处理下一个 image_item

    # -------------------------------------------------------------------------
    # 在复制前，将内存中的 coords (4角点) 与 sam2 marks 写入本地文件
    # -------------------------------------------------------------------------
    def _save_local_params_for_item(self, image_item):
        """
        示例：统一把 corners 存在 `_verified.txt` 文件里，
        并将 sam2 marks 也写进同一个文件的 <mark> 块。
        """
        base_no_ext, _ = os.path.splitext(image_item.image_path)
        verified_path = base_no_ext + "_verified.txt"

        # 1) 先写 4 corners
        TransformParams.save_to_file(verified_path, image_item.verified_coords)
        # 2) 再写 sam2 marks
        SamMarksParams.save_to_file(verified_path, image_item.sam2_marks)

    def _ask_conflict_resolution(self, conflict_filenames):
        """
        询问用户‘以下文件已存在，是否改名/跳过/忽略后续？’
        返回 'rename' / 'skip' / 'ignore'。
        """
        msg = QMessageBox(self.parent)
        msg.setWindowTitle("文件冲突")
        msg.setText(f"目标文件夹中已存在：\n{conflict_filenames}\n\n请选择操作：")
        rename_button = msg.addButton("改名", QMessageBox.AcceptRole)
        skip_button = msg.addButton("跳过", QMessageBox.RejectRole)
        ignore_button = msg.addButton("忽略后续冲突", QMessageBox.DestructiveRole)

        msg.exec()

        if msg.clickedButton() == rename_button:
            return "rename"
        elif msg.clickedButton() == ignore_button:
            return "ignore"
        else:
            return "skip"

    def _ask_new_basename(self, old_basename):
        """
        弹出输入框让用户填写新的“基础文件名”，不含扩展名。
        """
        new_name, ok = QInputDialog.getText(
            self.parent,
            "改名",
            f"原文件名：{old_basename}\n请输入新的文件名（不含扩展名）:"
        )
        if ok and new_name.strip():
            return new_name.strip()
        return None
