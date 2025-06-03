# my_perspective_app/controllers/main_controller.py

import os
from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QFileDialog, QMessageBox
from controllers.preview_controller import PreviewController
from controllers.resource_manager import ResourceManager
from controllers.sync_controller import SyncController
from controllers.settings_controller import SettingsController
from controllers.cache_manager import CacheManager
from models.param_file_manager import ParamFileManager

class MainController(QObject):
    """
    主控制器，负责与 MainWindow 交互，统筹：
    - ResourceManager (管理‘已加载’资源)
    - PreviewController (预览逻辑)
    - 目标文件夹选择
    - 程序退出时同步等
    - SettingsController (管理配置文件)
    - CacheManager (所有加载内容优先备份到本地 cache)
    """
    def __init__(self, main_window):
        # 注意：这里显式调用父类构造，传入 main_window 作为 parent（可选）
        super().__init__(main_window)
        self.main_window = main_window

        # 资源管理器
        self.resource_manager = ResourceManager()
        # 预览控制器
        self.preview_controller = PreviewController(main_window.preview_widget, self.resource_manager)

        # ========== SettingsController ==========
        # 计算出与 main.py 同目录下的 settings.txt
        # 假设 main.py 位于 ../ (即本文件所在 controllers/ 目录的上一级)
        # 所以：
        f_path = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
        base_dir = os.path.abspath(f_path)

        # ========== CacheManager ==========
        # 初始化时就创建 / 清空 cache 文件夹
        self.cache_manager = CacheManager(base_dir, main_window)

        # ========== SettingsController ==========
        # 假设 settings.txt 与 main.py 同级
        f_path = os.path.join(base_dir, 'settings.txt')
        self.local_settings_path = os.path.normpath(f_path)

        # 创建 SettingsController (若 settings.txt 不存在，会自动创建)
        self.settings_controller = SettingsController(self.local_settings_path)

        # ========== 连接菜单事件 ==========
        self.main_window.action_load_file.triggered.connect(self.load_file)
        self.main_window.action_load_folder.triggered.connect(self.load_folder)

        # ====== 监听 新增的菜单动作 ======
        self.main_window.action_save_to_folder.triggered.connect(self.save_to_target_folder)
        self.main_window.action_force_sync_folder.triggered.connect(self.force_sync_to_target_folder)
        self.main_window.action_close_program.triggered.connect(self.close_program)

        # 新增：点击“加载配置文件”菜单
        self.main_window.action_load_settings_file.triggered.connect(self.load_settings_file)
        # =================================

        # 监听“目标文件夹”选择事件
        self.main_window.folder_selector.folder_selected.connect(self.on_target_folder_selected)
        self.target_folder = ""

        # 让 main_window 自身安装事件过滤器 (我们这个 MainController)
        # 注意这里通常写 self.main_window.installEventFilter(self)
        # 而不是 self.main_window.parent().
        self.main_window.installEventFilter(self)

        # ========== 初始化画布高度 ==========
        self.canvas_height = self.settings_controller.get_canvas_height()
        # 将 side_panel 的滑动条值更新为当前设置
        self.main_window.side_panel.set_canvas_height(self.canvas_height)

        # 当 side_panel 中的滑动条改变 => 更新 settings + 更新 Preview
        self.main_window.side_panel.canvas_height_changed.connect(self._on_canvas_height_slider_changed)

    def _on_canvas_height_slider_changed(self, new_val):
        """
        当 side_panel 中的滑动条发生变化 => 更新 settings.txt + preview_controller
        """
        # 1) 更新 SettingsController
        self.settings_controller.set_canvas_height(new_val)
        # 2) 更新内存
        self.canvas_height = new_val
        # 3) 通知 preview
        self.preview_controller.set_canvas_height(new_val)


    # ======================
    #    加载配置文件
    # ======================
    def load_settings_file(self):
        """
        当用户选择“加载配置文件”菜单后，
        1) 先提示：建议先备份本地的配置文件
        2) 用户选中一个外部 settings.txt
        3) 用 settings_controller.overwrite_local_settings_with(...) 写回本地
        4) 更新 side_panel & preview_controller
        """
        # 弹窗提示
        msg_text = (f"在读取其它配置文件前，建议先备份本地的配置文件。\n"
                    f"当前配置文件路径：\n{self.local_settings_path}\n\n继续吗？")
        ret = QMessageBox.question(
            self.main_window,
            "提示",
            msg_text,
            QMessageBox.Yes | QMessageBox.No
        )
        if ret == QMessageBox.No:
            return  # 用户选择取消 => 不做任何处理

        file_dialog = QFileDialog(self.main_window, "选择设置文件 (settings.txt)")
        file_dialog.setNameFilters(["Text files (*.txt)", "All files (*)"])
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                external_path = selected_files[0]
                # 读取外部配置并覆盖写回本地
                self.settings_controller.overwrite_local_settings_with(external_path)

                # 重新获取画布高度
                self.canvas_height = self.settings_controller.get_canvas_height()
                # 更新 side_panel
                self.main_window.side_panel.set_canvas_height(self.canvas_height)
                # 更新 preview
                self.preview_controller.set_canvas_height(self.canvas_height)

                QMessageBox.information(
                    self.main_window,
                    "完成",
                    f"已从以下配置文件载入并覆盖本地：\n{external_path}"
                )

    # ==============================
    #  以下是资源加载/同步逻辑
    # ==============================

    def load_file(self):
        """
        “加载文件”菜单点击后，弹出对话框让用户选择图片文件
        """
        file_dialog = QFileDialog(self.main_window, "选择图片文件")
        file_dialog.setNameFilters(["Image files (*.png *.jpg *.jpeg *.bmp)", "All files (*)"])
        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                # (1) 将源文件先备份到 cache
                cache_paths = self.cache_manager.backup_files(selected_files)
                # (2) 添加到 ResourceManager
                self.resource_manager.add_images(cache_paths)
                # (3) 刷新预览
                self.preview_controller.refresh_thumbnails_and_display()

    def load_folder(self):
        """
        “加载整个文件夹”菜单点击后，选择文件夹
        """
        folder_path = QFileDialog.getExistingDirectory(self.main_window, "选择文件夹")
        if folder_path:
            self._load_folder_internal(folder_path)

    def on_target_folder_selected(self, folder_path):
        """
        当用户通过 FolderSelector 设置(或更改)了目标文件夹后，
        立即执行一次“加载整个文件夹”。
        """
        self.target_folder = folder_path
        self._load_folder_internal(folder_path)

    def _load_folder_internal(self, folder_path):
        """
        根据 folder_path 加载该目录下所有图片到已加载区
        """
        valid_ext = (".jpg", ".jpeg", ".png", ".bmp")
        files = []
        for f in os.listdir(folder_path):
            f_path = os.path.join(folder_path, f)
            f_path = os.path.normpath(f_path)
            _, ext = os.path.splitext(f)
            if ext.lower() in valid_ext:
                files.append(f_path)

        if files:
            # (1) 复制到 cache
            cache_paths = self.cache_manager.backup_files(files)
            # (2) 添加到资源管理
            self.resource_manager.add_images(cache_paths)

            # (2.5) 立刻为每个 image_item 读 `_verified.txt/.txt` 并填充
            self._eager_load_params()

            # (3) 刷新预览
            self.preview_controller.refresh_thumbnails_and_display()

    def _eager_load_params(self):
        """
        立刻为每个已加载的 image_item 去读取 _verified.txt / .txt，
        若不存在则给默认4角点 & 空 mark。
        """

        for item in self.resource_manager.get_all_images():
            if item.verified_coords is None:
                coords, marks = ParamFileManager.load_all(item.image_path)
                # 如果 coords是空 => 自定义默认4 corners
                if not coords:
                    coords = [
                        (0.25, 0.25),
                        (0.75, 0.25),
                        (0.75, 0.75),
                        (0.25, 0.75),
                    ]
                item.verified_coords = coords
                item.set_corners_from_coords(coords)

                item.sam2_marks = marks or []

    # ===================================================================
    #  “保存到目标文件夹” & “强制同步” 逻辑
    # ===================================================================

    def save_to_target_folder(self):
        """
        “保存到目标文件夹”：
        调用 SyncController(...).sync_resources_in_pairs()
        """
        if self.resource_manager.count() == 0:
            QMessageBox.information(self.main_window, "提示", "当前没有已加载的图片。")
            return
        if not self.target_folder:
            QMessageBox.warning(self.main_window, "警告", "尚未选择目标文件夹，请先选择。")
            return

        # 执行同步
        sync = SyncController(self.main_window)
        sync.sync_resources_in_pairs(self.resource_manager, self.target_folder)
        QMessageBox.information(self.main_window, "完成", "已保存并同步到目标文件夹。")

    def force_sync_to_target_folder(self):
        """
        “强制同步目标文件夹”：
            => 1) 清空文件夹
            => 2) 与普通保存相同：逐对复制 + 冲突询问
            但由于文件夹已空，基本不会出现冲突询问
        """
        if self.resource_manager.count() == 0:
            QMessageBox.information(self.main_window, "提示", "当前没有已加载的图片。")
            return
        if not self.target_folder:
            QMessageBox.warning(self.main_window, "警告", "尚未选择目标文件夹，请先选择。")
            return

        sync = SyncController(self.main_window)
        sync.force_sync_resources(self.resource_manager, self.target_folder)
        QMessageBox.information(self.main_window, "完成", "已强制同步到目标文件夹。")


    # ===================================================================
    #  关闭流程：弹出 5 个按钮的对话框
    # ===================================================================
    def close_program(self):
        """
        点击菜单“关闭程序” => 触发主窗口close()
        """
        self.main_window.close()

    def eventFilter(self, obj, event):
        if obj == self.main_window and event.type() == QEvent.Close:
            # 如果没有资源，直接让系统关
            if self.resource_manager.count() == 0:
                return super().eventFilter(obj, event)

            # ============ 自定义 5 按钮对话框 ============
            while True:
                msg_box = QMessageBox(self.main_window)
                msg_box.setWindowTitle("关闭前操作")
                msg_box.setText("是否将已加载内容保存到目标文件夹？\n\n请选择：")

                force_btn = msg_box.addButton("强制同步目标文件夹", QMessageBox.AcceptRole)
                save_btn = msg_box.addButton("保存到目标文件夹", QMessageBox.ActionRole)
                change_btn = msg_box.addButton("更改目标文件夹", QMessageBox.ActionRole)
                no_save_btn = msg_box.addButton("不保存", QMessageBox.DestructiveRole)
                cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

                msg_box.exec()

                clicked = msg_box.clickedButton()
                if clicked == force_btn:
                    # 强制同步
                    self.force_sync_to_target_folder()
                    # 然后再允许关闭
                    break
                elif clicked == save_btn:
                    # 普通保存到目标文件夹
                    self.save_to_target_folder()
                    break
                elif clicked == change_btn:
                    # 让用户重新选文件夹
                    folder_path = QFileDialog.getExistingDirectory(self.main_window, "选择新的目标文件夹")
                    if folder_path:
                        self.target_folder = folder_path
                    # 选完后回到 while True 重新询问
                    continue
                elif clicked == no_save_btn:
                    # 不保存 => 直接允许关闭
                    break
                elif clicked == cancel_btn:
                    # 取消 => 不关闭
                    event.ignore()
                    return True

            # 循环结束 => 用户做出了终止决定 => 允许关闭
        return super().eventFilter(obj, event)


    ## 目前无实际用途，可能后续添加调用：
    def _save_all_verified(self):
        """
        将 ResourceManager 中所有带 verified_coords 的图片写入 ..._verified.txt
        """
        images = self.resource_manager.get_all_images()
        for img in images:
            if img.verified_coords is not None:
                base, _ = os.path.splitext(img.image_path)
                verified_path = base + "_verified.txt"
                from models.transform_params import TransformParams
                TransformParams.save_to_file(verified_path, img.verified_coords)
        QMessageBox.information(self.main_window, "提示", "全部图片的已验证坐标已保存！")