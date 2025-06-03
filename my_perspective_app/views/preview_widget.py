# my_perspective_app/views/preview_widget.py
from PySide6.QtWidgets import QMenu, QToolButton

from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
    QScrollArea, QComboBox,QMessageBox
)
from PySide6.QtCore import Signal, Qt, QMimeData, QPoint
from PySide6.QtGui import (
    QPixmap, QPainter, QPen, QColor,
    QDragEnterEvent, QDropEvent, QWheelEvent, QMouseEvent
)
from models.transform_params import TransformParams
from controllers.shape_transform_controller import ShapeTransformController
from .thumbnail_bar import ThumbnailBar
from overlays.perspective_overlay import PerspectiveOverlay
from overlays.sam2_overlay import Sam2Overlay
from sam2_mask_generator import fake_mask_generator


class PreviewLabel(QLabel):
    """
    现在只负责：
      - 显示图像(可滚轮缩放)
      - 若有 current_overlay，则将 paintEvent / mouseEvent 代理给它
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)

        # 给自己一个灰色背景，方便看出边界
        self.setStyleSheet("background-color: #444; color: white;")
        self.setMinimumSize(400, 300)

        self.original_pixmap = None
        # 用于记录当前图的原尺寸
        self.original_width = 0
        self.original_height = 0
        self.scale_factor = 1.0

        self.current_overlay = None  # 可以设置成PerspectiveOverlay()等

    def set_overlay(self, overlay):
        """切换当前使用的Overlay对象(None表示不加载任何标记)"""
        self.current_overlay = overlay
        self.update()

    # -------------- 对外API --------------
    def load_image(self, image_path: str):
        if image_path:
            pix = QPixmap(image_path)
            self.original_pixmap = pix
            self.original_width = pix.width()
            self.original_height = pix.height()
        else:
            self.original_pixmap = None
            self.original_width = 0
            self.original_height = 0

        self.scale_factor = 1.0
        self._update_size()
        self.update()

    def _update_size(self):
        """
        根据 original_width/height 和 scale_factor，重新设置 label 的大小
        """
        # 让 label 的 size 变成这个，这样 scroll_area 可滚动
        scaled_w = max(1, int(self.original_width * self.scale_factor))
        scaled_h = max(1, int(self.original_height * self.scale_factor))

        self.resize(scaled_w, scaled_h)

    # -------------- 核心绘制 --------------
    def paintEvent(self, event):
        """
        先手动绘制 scaled_pixmap，然后(若 overlay_visible)再叠加四点和连线。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        if self.original_pixmap:
            # 1) 根据 scale_factor 计算图像的绘制尺寸
            scaled_w = int(self.original_width * self.scale_factor)
            scaled_h = int(self.original_height * self.scale_factor)

            # 2) 将原图缩放成 scaled_pixmap
            scaled_pixmap = self.original_pixmap.scaled(
                scaled_w, scaled_h,
                Qt.KeepAspectRatio,     # 保持宽高比
                Qt.SmoothTransformation # 平滑缩放
            )
            # 3) 画到左上角(0,0)，或你可居中也行
            painter.drawPixmap(0, 0, scaled_pixmap)

            # 4) 如果有 Overlay，就让它绘制
            if self.current_overlay:
                self.current_overlay.paint_overlay(painter, scaled_w, scaled_h)
        else:
            painter.drawText(self.rect(), Qt.AlignCenter, "无图片")

        painter.end()

    # -------------- 鼠标事件 --------------
    def mousePressEvent(self, event):
        if self.current_overlay:
            self.current_overlay.mouse_press_event(self, event)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.current_overlay:
            self.current_overlay.mouse_move_event(self, event)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.current_overlay:
            self.current_overlay.mouse_release_event(self, event)
        super().mouseReleaseEvent(event)

    # -------------- 滚轮事件 --------------
    def wheelEvent(self, event: QWheelEvent):
        """
        滚轮缩放：原图 和 形变参数 同步变化
        """
        # 滚轮缩放比例，可自行调整
        if event.angleDelta().y() > 0:
            # 滚轮向上 => 放大
            self.scale_factor *= 1.1
        else:
            # 滚轮向下 => 缩小
            self.scale_factor /= 1.1
            if self.scale_factor < 0.1:
                self.scale_factor = 0.1

        # 每次滚轮都更新 label 大小
        self._update_size()
        self.update()
        event.accept()

    def reset_scale_factor(self):
        self.scale_factor = 1.0
        self._update_size()
        self.update()

class PreviewWidget(QWidget):
    """
    上层容器，包含：
      - PreviewLabel(用于绘制图+形变框)
      - 按钮区域(上一张/下一张/加载隐藏参数/储存)
      - 缩略图栏(ThumbnailBar)
      - 拖拽文件处理
      - 发射对外的信号
    """
    """
    新版：将“加载透视变形参数”替换为一个模式下拉框 overlay_mode_selector，
    并把“形变参数保存”按钮仅在 mode=perspective 时可点击。
    """

    # 通用的 overlay_params_changed_signal(overlay_type, data)
    overlay_params_changed_signal = Signal(str, object)

    # 原本 file_dropped 等信号保持不变
    file_dropped = Signal(list)

    # 翻页信号
    request_previous = Signal()
    request_next = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setMinimumSize(600, 400)

        # 1) 用 QScrollArea 来装 PreviewLabel
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(False)
        # 注意：如果你想让scroll_area自动调大小，就设为 True，但这里我们想要出现滚动条
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)

        self.preview_label = PreviewLabel(self.scroll_area)
        self.scroll_area.setWidget(self.preview_label)

        # 2) 按钮区域
        self.btn_prev = QPushButton("上一张")
        self.btn_next = QPushButton("下一张")

        # 信号连接
        self.btn_prev.clicked.connect(self.request_previous)
        self.btn_next.clicked.connect(self.request_next)

        # 新增：下拉菜单
        self.overlay_mode_selector = QComboBox()
        self.overlay_mode_selector.addItem("不加载标记", userData="none")
        self.overlay_mode_selector.addItem("加载透视变形参数", userData="perspective")
        self.overlay_mode_selector.addItem("加载SAM2分割遮罩", userData="sam2")
        self.overlay_mode_selector.addItem("根据SAM2分割遮罩回归透视", userData="sam2_to_persp")
        # 默认选中 “不加载标记”
        self.overlay_mode_selector.setCurrentIndex(0)
        self.overlay_mode_selector.currentIndexChanged.connect(self._on_overlay_mode_changed)

        # 保存按钮（仅透视模式可用）
        self.btn_actions = QToolButton()
        self.btn_actions.setText("操作")  # 按钮标题
        self.btn_actions.setPopupMode(QToolButton.InstantPopup)

        # 构造一个 QMenu
        menu = QMenu(self)

        # 4 actions
        self.action_save_persp = menu.addAction("保存(仅透视)")
        self.action_load_mask = menu.addAction("加载mask")
        self.action_cancel_mask = menu.addAction("取消mask")
        self.action_refresh_mask = menu.addAction("刷新mask")

        # 将menu绑定到toolbutton
        self.btn_actions.setMenu(menu)

        # 连接 signals
        self.action_save_persp.triggered.connect(self._on_save_persp)
        self.action_load_mask.triggered.connect(self._on_load_mask)
        self.action_cancel_mask.triggered.connect(self._on_cancel_mask)
        self.action_refresh_mask.triggered.connect(self._on_refresh_mask)

        # 然后把 self.btn_actions 放进布局
        btn_layout = QHBoxLayout()

        # 3) 缩略图条
        self.thumbnail_bar = ThumbnailBar(self)

        # 4) 布局
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # 放入 scroll_area 而不是直接放 preview_label
        main_layout.addWidget(self.scroll_area, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_prev)
        btn_layout.addWidget(self.btn_next)
        btn_layout.addWidget(self.overlay_mode_selector)
        # btn_layout.addWidget(self.btn_save)  # 注释掉
        btn_layout.addWidget(self.btn_actions)

        main_layout.addLayout(btn_layout)

        main_layout.addWidget(self.thumbnail_bar, stretch=0)

        # 当前 overlay_mode
        self.current_overlay_mode = "none"
        # 可能的 Overlay 实例（在需要时创建/替换）
        self.perspective_overlay = None
        self.sam2_overlay = None
        # 其他 overlay (sam2...) 先留空

        # 连接 overlay 的信号 => 自己再发射
        # 由于 Overlay 实例会在切换时重新创建，这里在 set_overlay() 时会做连接

    # ------------------- Overlay 切换 -------------------
    def _on_overlay_mode_changed(self, index):
        new_mode = self.overlay_mode_selector.itemData(index)
        self.current_overlay_mode = new_mode

        # 根据模式，决定是否启用“保存”按钮
        # self.btn_actions.setEnabled(new_mode == "perspective")

        # 动态切换 PreviewLabel 的 overlay 对象
        if new_mode == "none":
            self.preview_label.set_overlay(None)

        elif new_mode == "perspective":
            if not self.perspective_overlay:
                # 如果还没创建，就创建一个
                # 在真正显示图片时，会再 set_image_item
                self.perspective_overlay = PerspectiveOverlay(None)
                # 连接 overlay 信号 => 自己转发
                self.perspective_overlay.overlay_params_changed_signal.connect(
                    self._on_overlay_params_changed
                )
            self.preview_label.set_overlay(self.perspective_overlay)

        elif new_mode == "sam2":
            if not self.sam2_overlay:
                
                self.sam2_overlay = Sam2Overlay(None)
                self.sam2_overlay.overlay_params_changed_signal.connect(
                    self._on_overlay_params_changed
                )
            self.preview_label.set_overlay(self.sam2_overlay)
        elif new_mode == "sam2_to_persp":
            # 占位
            self.preview_label.set_overlay(None)
        else:
            self.preview_label.set_overlay(None)

    def _on_overlay_params_changed(self, overlay_type, data):
        """
        来自某个overlay的参数变化。如 overlay_type="perspective", data=[(x1,y1),...].
        我们再往外发射
        """
        self.overlay_params_changed_signal.emit(overlay_type, data)

    # ------------------- 对外方法 -------------------
    def display_image(self, image_item, canvas_height=1000):
        """
        展示某张图片(或 None)。形变参数由相应 overlay 自行处理。
        """
        if not image_item:
            self.preview_label.load_image(None)
            self.preview_label.reset_scale_factor()
            # 若有 perspective_overlay，需要 set_image_item(None)
            if self.perspective_overlay:
                self.perspective_overlay.set_image_item(None)
            return

        # 加载原图
        self.preview_label.load_image(image_item.image_path)

        # -- 关键部分：根据 canvas_height 来设定一个初始缩放 --
        orig_h = self.preview_label.original_height
        if orig_h > 0:
            new_scale = canvas_height / orig_h
            new_scale = max(0.1, min(new_scale, 10.0))
            self.preview_label.scale_factor = new_scale
            self.preview_label._update_size()

        # 如果当前模式是 perspective，需要 set_image_item
        if self.current_overlay_mode == "perspective":
            if not self.perspective_overlay:
                self.perspective_overlay = PerspectiveOverlay(image_item)
                self.perspective_overlay.overlay_params_changed_signal.connect(
                    self._on_overlay_params_changed
                )
                self.preview_label.set_overlay(self.perspective_overlay)
            else:
                self.perspective_overlay.set_image_item(image_item)

        elif self.current_overlay_mode == "sam2":
            if not self.sam2_overlay:
                from overlays.sam2_overlay import Sam2Overlay
                self.sam2_overlay = Sam2Overlay(image_item)
                self.sam2_overlay.overlay_params_changed_signal.connect(
                    self._on_overlay_params_changed
                )
                self.preview_label.set_overlay(self.sam2_overlay)
            else:
                self.sam2_overlay.set_image_item(image_item)

        self.current_image = image_item  # 记住当前图
        self.preview_label.update()

    # ------------------- 保存 -------------------
    def _on_save_persp(self):
        """
        相当于原本的 _on_save_clicked()
        """
        if self.current_overlay_mode == "perspective":
            if self.perspective_overlay and self.perspective_overlay.image_item:
                coords_4 = self.perspective_overlay.image_item.get_coords_in_label_order()
                self.overlay_params_changed_signal.emit("perspective-save", coords_4)

    def _on_load_mask(self):
        """
        1) 如果当前模式不是 sam2，则可提示“仅sam2模式能加载mask”或直接无效。
        2) 否则 => 取当前 image_item
             => 如果 image_item.mask_pixmap 不存在 => 相当于点“刷新mask”
                否则 => 直接 set mask_visible=True
        3) 让 overlay 重新绘制
        """
        if self.current_overlay_mode != "sam2":
            return

        image_item = self._get_current_image_item()
        if not image_item:
            return

        if image_item.mask_pixmap is None:
            # 相当于先刷新
            self._refresh_mask_for_image_item(image_item)
        else:
            image_item.mask_visible = True

        self.preview_label.update()  # 重绘
    
    def _on_cancel_mask(self):
        """
        取消mask => set mask_visible=False
        """
        if self.current_overlay_mode != "sam2":
            return
        image_item = self._get_current_image_item()
        if not image_item:
            return
        image_item.mask_visible = False
        self.preview_label.update()

    def _on_refresh_mask(self):
        """
        手动点“刷新mask”，无论有无，都重新生成mask并显示
        """
        if self.current_overlay_mode != "sam2":
            return
        image_item = self._get_current_image_item()
        if not image_item:
            return
        self._refresh_mask_for_image_item(image_item)
        self.preview_label.update()

    def _refresh_mask_for_image_item(self, image_item):
        """
        这里调用“mask generator”占位逻辑:
         - 传入 image_item (包括sam2_marks)
         - 生成一个与原图相同大小, 并随机颜色的 QPixmap
         - 赋给 image_item.mask_pixmap
         - set mask_visible = True
        """
        pix = fake_mask_generator(image_item)
        image_item.mask_pixmap = pix
        image_item.mask_visible = True
        QMessageBox.information(self, "提示", "mask已更新完成")
        
    def _get_current_image_item(self):
        """
        返回 self.current_image，它在 display_image(...) 中被设置。
        """
        return self.current_image

    def _on_save_clicked(self):
        """
        仅在“加载透视变形参数”模式下使用。
        """
        if self.current_overlay_mode == "perspective":
            # 让 overlay 主动发射一次 overlay_params_changed_signal?
            # 或者只是在 PreviewController 里监听 overlay_params_changed_signal 后做写文件
            # 这里可自行决定。示例：直接通知外部控制器
            # 也可以在 overlay 内部再保存...
            # 暂时就发个信号“手动保存”
            if self.perspective_overlay and self.perspective_overlay.image_item:
                coords_4 = self.perspective_overlay.image_item.get_coords_in_label_order()
                self.overlay_params_changed_signal.emit("perspective-save", coords_4)
        else:
            pass  # 其它模式下无效

    # ------------------- 拖拽事件 -------------------

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls]
        self.file_dropped.emit(paths)
        event.acceptProposedAction()
        super().dropEvent(event)