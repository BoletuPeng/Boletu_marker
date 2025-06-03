# my_perspective_app/sam2_mask_generator.py

import os
import random
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage, QPixmap, QPainter, QColor
from PySide6.QtCore import Qt

from sam2.build_sam import build_sam2
from sam2.sam2_image_predictor import SAM2ImagePredictor


# ----- 全局变量：SAM2 模型 & 预测器 -----
_sam2_predictor = None
_sam2_inited = False

def _init_sam2_model(
    checkpoint_path: str = "sam2/checkpoints/sam2.1_hiera_large.pt",
    config_path: str = "sam2/checkpoints/sam2.1_hiera_large.yaml",
    device_str: str = "cuda"
):
    """
    只在第一次需要时加载SAM2模型。
    checkpoint_path, config_path 根据你实际路径做调整。
    """
    global _sam2_predictor, _sam2_inited

    if _sam2_inited:
        return  # 已经加载过，直接返回

    if build_sam2 is None or SAM2ImagePredictor is None:
        print("[WARNING] sam2 not installed or import failed. Will use fallback logic.")
        _sam2_inited = True
        return
    
    # 根据官方示例加载
    print("[INFO] Initializing SAM2 model ...")
    import torch

    sam2_model = build_sam2(config_path, checkpoint_path, device=torch.device(device_str))
    _sam2_predictor = SAM2ImagePredictor(sam2_model)
    _sam2_inited = True
    print("[INFO] SAM2 model initialized successfully.")

def fake_mask_generator(image_item):
    """
    供外部调用的统一函数：
      - 若尚未加载SAM2模型，则先调用 _init_sam2_model()
      - 从 image_item.image_path 中读图 => 解析 image_item.sam2_marks => 生成 mask => 转成 QPixmap
      - 返回 QPixmap (若sam2不可用，就返回一个随机半透明覆盖)
    """

    # 0) 确保SAM2已经初始化
    _init_sam2_model()  

    # 若 _sam2_predictor is None => 说明 sam2导入失败 => 就用一个随机覆盖
    if _sam2_predictor is None:
        print("[WARNING] SAM2 predictor not available, fallback to random fill.")
        return _random_fill_mask(image_item)

    # 1) 读取原图 => numpy array
    pil_img = Image.open(image_item.image_path).convert("RGB")
    image_np = np.array(pil_img)
    h, w, _ = image_np.shape

    # 2) 解析 image_item.sam2_marks => 构造 SAM2 的 point_coords, point_labels, boxes
    #    我们只演示 pos/neg 点，框暂不详细处理(若你要可自行添加).
    point_coords, point_labels = [], []
    # TODO: box_list = []

    for (rx, ry, label_str) in image_item.sam2_marks:
        x_px = int(rx * w)
        y_px = int(ry * h)
        if label_str == "pos":
            point_coords.append([x_px, y_px])
            point_labels.append(1)
        elif label_str == "neg":
            point_coords.append([x_px, y_px])
            point_labels.append(0)
        else:
            # 如果 label_str = "0_0" ... => 说明是框角
            # 你可以等 _group_box_points 里组装成 xyxy 再预测
            pass

    point_coords = np.array(point_coords, dtype=np.int32)
    point_labels = np.array(point_labels, dtype=np.int32)

    # 3) 调用 predictor
    #    set_image => predict
    _sam2_predictor.set_image(image_np)
    if len(point_coords) == 0:
        # 若没有点 => 直接返回空pixmap
        return _make_transparent_mask(w,h)

    masks, scores, _ = _sam2_predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        # box=xxx, # 如果你还想传 box
        multimask_output=False
    )
    # masks.shape => (#masks, h, w)
    # scores.shape => (#masks,)

    if len(masks) == 0:
        # 没预测到 => return a transparent
        return _make_transparent_mask(w,h)

    # 4) 选score最高的
    best_idx = np.argmax(scores)
    best_mask = masks[best_idx]  # (h,w) bool/float

    # 5) 转成 QPixmap (RGBA)
    color_mask_rgba = _build_rgba_mask(best_mask)
    qimg = QImage(color_mask_rgba.data, w, h, QImage.Format_RGBA8888)
    qpix = QPixmap.fromImage(qimg)
    return qpix

# ---------------------------------------------------------------------------
# 内部辅助：若sam2不可用，就返回一个随机半透明覆盖
# ---------------------------------------------------------------------------
def _random_fill_mask(image_item):
    """
    若sam2无法使用，则与原'_fake_mask_generator'逻辑类似：
    读图大小 => 全图随机颜色 => QPixmap
    """
    pil_img = Image.open(image_item.image_path).convert("RGB")
    w, h = pil_img.size

    # 构建 RGBA np.array
    mask_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    # 填充
    c = (random.randint(0,255), random.randint(0,255), random.randint(0,255), 100)
    mask_rgba[..., 0] = c[0]
    mask_rgba[..., 1] = c[1]
    mask_rgba[..., 2] = c[2]
    mask_rgba[..., 3] = c[3]

    qimg = QImage(mask_rgba.data, w, h, QImage.Format_RGBA8888)
    qpix = QPixmap.fromImage(qimg)
    return qpix

def _make_transparent_mask(width, height):
    """
    返回一个完全透明的 pixmap
    """
    mask_rgba = np.zeros((height, width, 4), dtype=np.uint8)
    qimg = QImage(mask_rgba.data, width, height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)

def _build_rgba_mask(mask_array):
    """
    mask_array: shape (h,w), bool/float
    把 =1 的位置做个颜色, 其它透明 => RGBA
    """
    # 如果 mask_array 是 float, threshold 0.5
    mask_bin = (mask_array > 0.5).astype(np.uint8)

    h, w = mask_bin.shape
    mask_rgba = np.zeros((h, w, 4), dtype=np.uint8)

    # 前景用随机色 or 固定色
    color = (30,144,255,120)  # RGBA (半透明蓝)
    mask_rgba[mask_bin == 1, 0] = color[0]  # R
    mask_rgba[mask_bin == 1, 1] = color[1]  # G
    mask_rgba[mask_bin == 1, 2] = color[2]  # B
    mask_rgba[mask_bin == 1, 3] = color[3]  # A

    return mask_rgba
