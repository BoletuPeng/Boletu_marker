# my_perspective_app/controllers/resource_manager.py

import os
from models.image_item import ImageItem

class ResourceManager:
    """
    统一管理‘已加载区’的资源，可多次加载来自不同文件夹、文件或拖拽的图片。
    """
    def __init__(self):
        self.loaded_images = []  # 存放 ImageItem 的列表
    
    def add_images(self, image_paths):
        """
        批量添加图片资源
        """
        for p in image_paths:
            # 确保不重复
            if p and (not any(item.image_path == p for item in self.loaded_images)):
                self.loaded_images.append(ImageItem(p))
    
    def remove_image(self, index):
        """
        根据索引移除已加载区中的图片
        """
        if 0 <= index < len(self.loaded_images):
            self.loaded_images.pop(index)
    
    def clear(self):
        """
        清空所有加载资源
        """
        self.loaded_images.clear()

    def get_all_images(self):
        return self.loaded_images

    def count(self):
        return len(self.loaded_images)