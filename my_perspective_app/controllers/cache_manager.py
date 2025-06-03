# my_perspective_app/controllers/cache_manager.py

import os
import shutil
from PySide6.QtWidgets import QMessageBox

class CacheManager:
    """
    CacheManager 负责在本地项目目录中创建并清空一个 'cache' 文件夹，
    并提供 backup_files(...) 接口，将外部加载的图片及其关联的 txt 文件
    复制到此缓存文件夹中，后续所有操作都从 cache 中读取。
    """
    def __init__(self, base_dir, parent_widget=None):
        """
        :param base_dir: 通常是 main.py 所在目录
        :param parent_widget: 用于弹出错误提示的父级 widget（可为 MainWindow）
        """
        self.parent_widget = parent_widget
        self.cache_folder = os.path.join(base_dir, "cache")

        # 如果不存在，就创建；如果已存在，则清空（删除其中所有文件和子文件夹）
        if not os.path.exists(self.cache_folder):
            os.makedirs(self.cache_folder)
        else:
            self._clear_folder(self.cache_folder)

    def _clear_folder(self, folder):
        """删除 folder 中的所有文件及子文件夹。"""
        for item in os.listdir(folder):
            item_path = os.path.join(folder, item)
            if os.path.isfile(item_path) or os.path.islink(item_path):
                os.remove(item_path)
            else:
                shutil.rmtree(item_path)

    def backup_files(self, file_paths):
        """
        将用户选定（或拖拽）的文件复制到 cache 文件夹中，并返回这些文件在 cache 中的新路径列表。
        同时会检查是否存在与图片同名（仅去掉扩展名后）的 .txt 或 _verified.txt 文件，若存在也复制到 cache。
        """
        new_paths = []
        for src_path in file_paths:
            # 1) 先复制图片本身到 cache
            local_image_path = self._copy_to_cache(src_path)
            new_paths.append(local_image_path)

            # 2) 检查同名的 .txt / _verified.txt 文件
            base_no_ext, _ = os.path.splitext(src_path)
            for possible_ext in [".txt", "_verified.txt"]:
                possible_param = base_no_ext + possible_ext
                if os.path.exists(possible_param):
                    # 复制该参数文件到 cache（不需要记录在 new_paths，因为 ResourceManager 主要关心图片）
                    self._copy_to_cache(possible_param)

        return new_paths

    def _copy_to_cache(self, src_path):
        """
        核心复制方法：将 src_path 复制到 cache 文件夹下，若重名则自动改名，
        返回在 cache 文件夹中的新路径。
        """
        if not os.path.isfile(src_path):
            return ""  # 如果不是文件（可能是文件夹或不存在），可根据需要选择忽略或提示
        
        base_name = os.path.basename(src_path)
        dst_path = os.path.join(self.cache_folder, base_name)
        dst_path = self._get_unique_path(dst_path)  # 防止重名

        try:
            shutil.copy2(src_path, dst_path)
        except Exception as e:
            if self.parent_widget:
                QMessageBox.warning(self.parent_widget, "错误", f"备份文件失败:\n{src_path}\n{str(e)}")
            return ""
        
        return dst_path

    def _get_unique_path(self, path):
        """
        如果 path 已存在，则追加数字后缀，使之唯一。
        例如 cache/xxx.jpg 已存在，则自动变为 cache/xxx_1.jpg, xxx_2.jpg, ...
        """
        if not os.path.exists(path):
            return path

        base, ext = os.path.splitext(path)
        counter = 1
        new_path = f"{base}_{counter}{ext}"
        while os.path.exists(new_path):
            counter += 1
            new_path = f"{base}_{counter}{ext}"
        return new_path
