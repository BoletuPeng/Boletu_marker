# my_perspective_app/controllers/preview_controller.py

import os
from models.transform_params import TransformParams
from models.sam_marks_params import SamMarksParams
from models.image_item import ImageItem
from PySide6.QtWidgets import QWidget

from controllers.shape_transform_controller import ShapeTransformController

class PreviewController:
    """
    PreviewController 负责将 ResourceManager 中的图片显示到 PreviewWidget，
    并管理缩略图的交互（点击、右键移除等）。
    """
    def __init__(self, preview_widget, resource_manager):
        """
        :param preview_widget: 预览的 UI 对象 (PreviewWidget)
        :param resource_manager: 全局的资源管理器 (ResourceManager)
        """
        self.current_canvas_height = 600  # 一个默认初始值

        self.preview_widget = preview_widget
        self.resource_manager = resource_manager
        
        # 当前在“已加载区”中的索引
        self.current_index = 0

        # 连接缩略图事件
        self.preview_widget.thumbnail_bar.thumbnail_clicked.connect(self.on_thumbnail_clicked)
        self.preview_widget.thumbnail_bar.thumbnail_removed.connect(self.on_thumbnail_removed)
        
        # 连接翻页按钮（如有的话），或在 preview_widget 中还有 signal
        self.preview_widget.request_previous.connect(self.show_previous_image)
        self.preview_widget.request_next.connect(self.show_next_image)

        # 监听拖拽进来的文件
        self.preview_widget.file_dropped.connect(self.on_file_dropped)

        # 监听 overlay_params_changed_signal
        self.preview_widget.overlay_params_changed_signal.connect(self.on_overlay_params_changed)

    def set_canvas_height(self, height):
        """由 MainController 或其他地方调用，以更新当前预期的画布高度。"""
        self.current_canvas_height = height

    def refresh_thumbnails_and_display(self):
        """
        当“已加载区”更新（ResourceManager 里有新的或移除的图片）时，
        调用此函数刷新缩略图并显示当前图片。
        """
        # 如果 current_index 越界（比如移除了图片），重置为 0
        if self.current_index >= self.resource_manager.count():
            self.current_index = 0

        # 获取已加载的所有图片
        image_items = self.resource_manager.get_all_images()
        
        # 若列表为空，则清空预览并返回
        if not image_items:
            self.preview_widget.thumbnail_bar.set_thumbnails([])
            self.preview_widget.display_image(None)
            return
        
        # 构建图片路径列表，交给 thumbnail_bar
        all_paths = [item.image_path for item in image_items]
        self.preview_widget.thumbnail_bar.set_thumbnails(all_paths)
        
        # 先高亮当前 index
        self.preview_widget.thumbnail_bar.set_current_index(self.current_index)

        # 显示当前索引对应的图片
        self._display_image(self.current_index)

    def on_thumbnail_clicked(self, index):
        """
        当用户在缩略图上左键点击某张图片时，切换当前预览到该图片。
        """
        self.current_index = index
        self._display_image(index)
        # 再次更新红框
        self.preview_widget.thumbnail_bar.set_current_index(self.current_index)

    def on_thumbnail_removed(self, index):
        """
        当用户在缩略图上右键菜单选择“移除”时，删除该图片并刷新。
        """
        self.resource_manager.remove_image(index)
        # 如果移除的 index < current_index，会影响当前索引，需要适当修正
        if index < self.current_index:
            self.current_index -= 1
        self.refresh_thumbnails_and_display()

    def _display_image(self, index):
        image_items = self.resource_manager.get_all_images()
        if index < 0 or index >= len(image_items):
            return
        
        image_item = image_items[index]

        # -----------------------------
        # 使用 ParamFileManager 统一读取
        # -----------------------------
        from models.param_file_manager import ParamFileManager
        coords, marks = ParamFileManager.load_all(image_item.image_path)

        # 把 4 corners 存到 image_item
        image_item.verified_coords = coords
        image_item.set_corners_from_coords(coords)

        # 把 sam2 marks 存到 image_item
        image_item.sam2_marks = marks

        # -----------------------------
        # 显示到预览控件
        # -----------------------------
        self.preview_widget.display_image(
            image_item, 
            canvas_height=self.current_canvas_height
        )

    def show_previous_image(self):
        """
        点击‘上一张’按钮时：切换到前一张图片。
        """
        if self.resource_manager.count() == 0:
            return
        self.current_index = max(0, self.current_index - 1)
        self._display_image(self.current_index)
        self.preview_widget.thumbnail_bar.set_current_index(self.current_index)

    def show_next_image(self):
        """
        点击‘下一张’按钮时：切换到下一张图片。
        """
        if self.resource_manager.count() == 0:
            return
        self.current_index = min(self.resource_manager.count() - 1, self.current_index + 1)
        self._display_image(self.current_index)
        self.preview_widget.thumbnail_bar.set_current_index(self.current_index)

    def on_overlay_params_changed(self, overlay_type, data):
        image_items = self.resource_manager.get_all_images()
        if not image_items or self.current_index < 0 or self.current_index >= len(image_items):
            return
        current_image = image_items[self.current_index]

        if overlay_type in ("perspective", "perspective-save"):
            # data => [(x1,y1), (x2,y2), (x3,y3), (x4,y4)]
            current_image.verified_coords = data

        elif overlay_type == "sam2":
            # data => [(x,y,label), ...]
            current_image.sam2_marks = data

        # 这里可能还会有 sam2_to_persp 等

        # ------ 统一写回文件 ------
        base, _ = os.path.splitext(current_image.image_path)
        verified_path = base + "_verified.txt"

        # 把内存中的 coords + marks 全部一次性写进去
        from models.param_file_manager import ParamFileManager
        ParamFileManager.save_all(
            verified_path,
            current_image.verified_coords,
            current_image.sam2_marks
        )


    def on_file_dropped(self, paths):
        """
        当用户在 PreviewWidget 中拖拽文件进来时，添加到已加载区并刷新。
        """
        self.resource_manager.add_images(paths)
        self.refresh_thumbnails_and_display()
