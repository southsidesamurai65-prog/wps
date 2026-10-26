"""文档扫描：把手机拍的照片变成「扫描件」。

管线：边缘检测 → 透视矫正 → 滤镜增强 → 旋转 → 纸张排版 → 手写签名 → PDF。

全部本地处理，不联网。对外 API 都是纯函数，方便 UI 与测试复用；图片一律用
Pillow 读写，避免 OpenCV 在中文路径下 ``imread/imwrite`` 静默失败。
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import cv2
import fitz
import numpy as np
from PIL import Image, ImageOps

from wps_tool.core.errors import ConversionError

FILTERS: dict[str, str] = {
    "original": "原图",
    "enhance": "增强",
    "gray": "灰度",
    "bw": "黑白",
}

PAPER_SIZES_MM: dict[str, tuple[float, float]] = {
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
}

SIGNATURE_ANCHORS = (
    "bottom-right",
    "bottom-left",
    "top-right",
    "top-left",
    "center",
)


@dataclass(frozen=True)
class Signature:
    """手写签名：透明 PNG + 在页面上的锚点/宽度/透明度。"""

    png: bytes
    anchor: str = "bottom-right"
    width_ratio: float = 0.28
    margin_ratio: float = 0.04
    opacity: float = 1.0


@dataclass
class ScanPage:
    """一页扫描件。

    ``corners`` 是原图坐标系下的归一化四角（TL/TR/BR/BL，取值 0..1），
    这样同一份坐标既能用于缩略图预览，也能用于全分辨率导出。
    """

    source_path: str
    corners: np.ndarray
    filter: str = "enhance"
    rotation: int = 0
    signature: Signature | None = None


# ===== 图片读取 =====


def load_image(path: str, max_dim: int | None = None) -> np.ndarray:
    """读取图片为 RGB ``uint8`` 数组，自动处理 EXIF 方向；``max_dim`` 可限制最长边。"""
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            if max_dim and max(im.size) > max_dim:
                im.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            rgb = im.convert("RGB")
            return np.asarray(rgb, dtype=np.uint8).copy()
    except (OSError, ValueError) as exc:
        raise ConversionError(f"无法读取图片：{Path(path).name}（{exc}）") from exc


# ===== 边缘检测 / 透视矫正 =====


def order_corners(points: Sequence[Sequence[float]]) -> np.ndarray:
    """把四个点排成 TL、TR、BR、BL（左上、右上、右下、左下）。"""
    pts = np.asarray(points, dtype=np.float32).reshape(4, 2)
    if not np.isfinite(pts).all():
        raise ConversionError("文档四角坐标无效")
    sums = pts.sum(axis=1)
    diffs = pts[:, 1] - pts[:, 0]
    tl = pts[int(np.argmin(sums))]
    br = pts[int(np.argmax(sums))]
    tr = pts[int(np.argmin(diffs))]
    bl = pts[int(np.argmax(diffs))]
    return np.array([tl, tr, br, bl], dtype=np.float32)


def _as_pixel_corners(corners: np.ndarray, width: int, height: int) -> np.ndarray:
    """接受归一化坐标（0..1）或像素坐标，返回排好序的像素坐标。"""
    pts = np.asarray(corners, dtype=np.float32)
    if pts.shape != (4, 2):
        raise ConversionError("文档四角必须是 4 个点")
    if np.nanmax(np.abs(pts)) <= 2.0:
        pts = pts * np.array([width, height], dtype=np.float32)
    pts = order_corners(pts)
    pts[:, 0] = np.clip(pts[:, 0], 0, max(0, width - 1))
    pts[:, 1] = np.clip(pts[:, 1], 0, max(0, height - 1))
    return pts


def _quad_from_contour(contour: np.ndarray, image_area: float) -> np.ndarray | None:
    """尝试把一条轮廓变成四边形；失败返回 None。"""
    area = float(cv2.contourArea(contour))
    if area < image_area * 0.12:
        return None
    peri = float(cv2.arcLength(contour, True))
    if peri <= 0:
        return None
    approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
    if len(approx) == 4 and cv2.isContourConvex(approx):
        quad = approx.reshape(4, 2).astype(np.float32)
    else:
        rect = cv2.minAreaRect(contour)
        (_, _), (rw, rh), _ = rect
        if min(rw, rh) <= 0:
            return None
        if min(rw, rh) < 0.12 * max(np.sqrt(image_area), 1.0):
            return None
        quad = cv2.boxPoints(rect).astype(np.float32)
    if abs(float(cv2.contourArea(quad))) < image_area * 0.12:
        return None
    return quad


def _find_document_quad(gray: np.ndarray) -> np.ndarray | None:
    """多策略找文档四边形：Canny / Otsu / 自适应阈值。"""
    image_area = float(gray.shape[0] * gray.shape[1])
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    median = float(np.median(blurred))
    lower = int(max(0, 0.66 * median))
    upper = int(min(255, max(lower + 20, 1.33 * median)))
    _, otsu = cv2.threshold(
        blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    adaptive = cv2.adaptiveThreshold(
        blurred,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )
    edge_maps = (
        cv2.Canny(blurred, lower, upper),
        otsu,
        adaptive,
    )
    kernel = np.ones((5, 5), np.uint8)
    height, width = gray.shape[:2]
    best: np.ndarray | None = None
    best_area = 0.0
    fallback: np.ndarray | None = None
    fallback_area = 0.0
    for edges in edge_maps:
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
            try:
                quad = _quad_from_contour(contour, image_area)
            except cv2.error:
                continue
            if quad is None:
                continue
            area = abs(float(cv2.contourArea(quad)))
            xs, ys = quad[:, 0], quad[:, 1]
            touches_border = (
                xs.min() <= 2
                and ys.min() <= 2
                and xs.max() >= width - 3
                and ys.max() >= height - 3
            )
            if touches_border:
                if area > fallback_area:
                    fallback = quad
                    fallback_area = area
                continue
            if area > best_area:
                best = quad
                best_area = area
    return best if best is not None else fallback


def detect_document_corners(
    rgb: np.ndarray, max_dim: int = 1600
) -> np.ndarray | None:
    """检测文档四角，返回归一化 TL/TR/BR/BL；检测不到返回 ``None``。"""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ConversionError("边缘检测需要 RGB 三通道图片")
    height, width = rgb.shape[:2]
    if height < 20 or width < 20:
        return None
    scale = min(1.0, max_dim / max(height, width))
    small = (
        cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        if scale < 1.0
        else rgb
    )
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    quad = _find_document_quad(gray)
    if quad is None:
        return None
    quad = order_corners(quad)
    sh, sw = small.shape[:2]
    quad[:, 0] = np.clip(quad[:, 0] / sw, 0.0, 1.0)
    quad[:, 1] = np.clip(quad[:, 1] / sh, 0.0, 1.0)
    return quad.astype(np.float32)


def warp_document(rgb: np.ndarray, corners: np.ndarray, max_side: int = 8000) -> np.ndarray:
    """按四角做透视矫正，返回正向的文档图片。"""
    height, width = rgb.shape[:2]
    pts = _as_pixel_corners(corners, width, height)
    tl, tr, br, bl = pts
    width_top = float(np.linalg.norm(tr - tl))
    width_bottom = float(np.linalg.norm(br - bl))
    height_left = float(np.linalg.norm(bl - tl))
    height_right = float(np.linalg.norm(br - tr))
    out_w = round(max(width_top, width_bottom))
    out_h = round(max(height_left, height_right))
    if out_w < 8 or out_h < 8:
        return rgb.copy()
    scale = min(1.0, max_side / max(out_w, out_h))
    if scale < 1.0:
        out_w = max(1, round(out_w * scale))
        out_h = max(1, round(out_h * scale))
    dst = np.array(
        [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
        dtype=np.float32,
    )
    matrix = cv2.getPerspectiveTransform(pts, dst)
    return cv2.warpPerspective(
        rgb,
        matrix,
        (out_w, out_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


# ===== 滤镜增强 =====


def _normalized_gray(rgb: np.ndarray) -> np.ndarray:
    """用大尺度背景估计做光照归一化，压掉阴影和纸面渐变。"""
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    sigma = max(8.0, max(gray.shape) / 30.0)
    background = cv2.GaussianBlur(gray, (0, 0), sigmaX=sigma, sigmaY=sigma)
    return cv2.divide(gray, background, scale=255)


def enhance_document(rgb: np.ndarray, mode: str) -> np.ndarray:
    """按滤镜处理图片：original / enhance / gray / bw。"""
    mode = (mode or "enhance").lower()
    if mode not in FILTERS:
        raise ConversionError(f"未知扫描滤镜：{mode}")
    if mode == "original":
        return rgb.copy()

    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    norm = _normalized_gray(rgb)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    if mode == "gray":
        return cv2.cvtColor(clahe.apply(norm), cv2.COLOR_GRAY2RGB)

    if mode == "bw":
        block = int(max(15, min(99, (min(gray.shape) // 40) | 1)))
        binary = cv2.adaptiveThreshold(
            norm,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            block,
            12,
        )
        return cv2.cvtColor(binary, cv2.COLOR_GRAY2RGB)

    gain = norm.astype(np.float32) / np.maximum(gray.astype(np.float32), 1.0)
    gain = np.clip(gain, 0.55, 2.2)
    enhanced = np.clip(
        rgb.astype(np.float32) * gain[:, :, None], 0, 255
    ).astype(np.uint8)
    lab = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
    lightness, a, b = cv2.split(lab)
    lightness = clahe.apply(lightness)
    enhanced = cv2.cvtColor(
        cv2.merge((lightness, a, b)), cv2.COLOR_LAB2RGB
    )
    blurred = cv2.GaussianBlur(enhanced, (0, 0), 1.2)
    return cv2.addWeighted(enhanced, 1.3, blurred, -0.3, 0)


def rotate_rgb(rgb: np.ndarray, rotation: int) -> np.ndarray:
    """顺时针旋转 0/90/180/270 度。"""
    rotation = int(rotation) % 360
    if rotation not in (0, 90, 180, 270):
        raise ConversionError("扫描页旋转角度只支持 0/90/180/270")
    if rotation == 0:
        return rgb
    return np.ascontiguousarray(np.rot90(rgb, k=-(rotation // 90)))


# ===== 签名 =====


def apply_signature(img: Image.Image, signature: Signature) -> Image.Image:
    """把透明签名 PNG 合成到页面上（按锚点与页面比例定位）。"""
    if not signature.png:
        return img
    try:
        with Image.open(BytesIO(signature.png)) as raw:
            sig = raw.convert("RGBA")
    except (OSError, ValueError) as exc:
        raise ConversionError(f"签名图片无效：{exc}") from exc

    opacity = float(np.clip(signature.opacity, 0.0, 1.0))
    if opacity < 1.0:
        alpha = sig.getchannel("A").point(lambda value: int(value * opacity))
        sig.putalpha(alpha)

    page_w, page_h = img.size
    margin = round(min(page_w, page_h) * max(0.0, signature.margin_ratio))
    max_w = max(1, page_w - 2 * margin)
    max_h = max(1, page_h - 2 * margin)
    target_w = max(1, round(page_w * min(max(signature.width_ratio, 0.02), 0.9)))
    target_h = max(1, round(target_w * sig.height / max(sig.width, 1)))
    if target_w > max_w:
        target_w = max_w
        target_h = max(1, round(target_w * sig.height / max(sig.width, 1)))
    if target_h > max_h:
        target_h = max_h
        target_w = max(1, round(target_h * sig.width / max(sig.height, 1)))
    sig = sig.resize((target_w, target_h), Image.Resampling.LANCZOS)

    anchor = signature.anchor if signature.anchor in SIGNATURE_ANCHORS else "bottom-right"
    if anchor == "bottom-right":
        x, y = page_w - margin - target_w, page_h - margin - target_h
    elif anchor == "bottom-left":
        x, y = margin, page_h - margin - target_h
    elif anchor == "top-right":
        x, y = page_w - margin - target_w, margin
    elif anchor == "top-left":
        x, y = margin, margin
    else:
        x, y = (page_w - target_w) // 2, (page_h - target_h) // 2

    base = img.convert("RGBA")
    base.alpha_composite(sig, (max(0, x), max(0, y)))
    return base.convert("RGB")


# ===== 页面排版 / 导出 =====


def _paper_pixels(paper: str, dpi: int) -> tuple[int, int]:
    paper = paper.lower()
    landscape = paper.endswith("-landscape")
    base = paper[: -len("-landscape")] if landscape else paper
    if base not in PAPER_SIZES_MM:
        raise ConversionError(f"未知纸张：{paper}")
    width_mm, height_mm = PAPER_SIZES_MM[base]
    if landscape:
        width_mm, height_mm = height_mm, width_mm
    return (
        round(width_mm / 25.4 * dpi),
        round(height_mm / 25.4 * dpi),
    )


def _fit_on_paper(img: Image.Image, target: tuple[int, int]) -> Image.Image:
    target_w, target_h = target
    scale = min(target_w / img.width, target_h / img.height)
    new_w = max(1, round(img.width * scale))
    new_h = max(1, round(img.height * scale))
    resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), "white")
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def render_page(
    page: ScanPage,
    *,
    dpi: int = 300,
    paper: str = "a4",
    source_rgb: np.ndarray | None = None,
    include_signature: bool = True,
) -> Image.Image:
    """渲染一页为 PIL 图片（预览和导出共用）。"""
    if dpi < 50 or dpi > 600:
        raise ConversionError("DPI 需在 50..600 之间")
    if paper != "auto" and paper not in (
        "a4",
        "letter",
        "a4-landscape",
        "letter-landscape",
    ):
        raise ConversionError(f"未知纸张：{paper}")
    rgb = load_image(page.source_path) if source_rgb is None else source_rgb
    rgb = warp_document(rgb, page.corners)
    rgb = enhance_document(rgb, page.filter)
    rgb = rotate_rgb(rgb, page.rotation)
    img = Image.fromarray(np.ascontiguousarray(rgb), "RGB")
    if paper != "auto":
        img = _fit_on_paper(img, _paper_pixels(paper, dpi))
    if include_signature and page.signature is not None:
        img = apply_signature(img, page.signature)
    return img


def export_scan_pdf(
    pages: Sequence[ScanPage],
    output_path: str,
    *,
    dpi: int = 300,
    paper: str = "a4",
    quality: int = 88,
    title: str | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> str:
    """把多页扫描件导出为 PDF。

    加密、水印请导出后在主界面用对应的 PDF 功能处理，避免与扫描流程重复。
    """
    pages = list(pages)
    if not pages:
        raise ConversionError("没有可导出的页面")
    quality = int(np.clip(quality, 1, 95))
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    try:
        total = len(pages)
        for index, page in enumerate(pages, start=1):
            img = render_page(page, dpi=dpi, paper=paper)
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=quality, optimize=True)
            page_width = img.width / dpi * 72
            page_height = img.height / dpi * 72
            pdf_page = doc.new_page(width=page_width, height=page_height)
            pdf_page.insert_image(pdf_page.rect, stream=buffer.getvalue())
            if progress is not None:
                progress(index, total)
        doc.set_metadata(
            {
                "title": title or out.stem,
                "producer": "wps-tool",
                "creator": "wps-tool 文档扫描",
            }
        )
        doc.save(str(out), deflate=True, garbage=3)
    finally:
        doc.close()
    return str(out)


def export_scan_images(
    pages: Sequence[ScanPage],
    output_dir: str,
    *,
    fmt: str = "jpg",
    dpi: int = 300,
    paper: str = "a4",
    quality: int = 88,
    progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """把多页扫描件导出为图片，返回按页序排列的路径列表。"""
    pages = list(pages)
    if not pages:
        raise ConversionError("没有可导出的页面")
    fmt = fmt.lower()
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt not in ("jpg", "png"):
        raise ConversionError("扫描图片只支持 jpg / png")
    quality = int(np.clip(quality, 1, 95))
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    total = len(pages)
    for index, page in enumerate(pages, start=1):
        img = render_page(page, dpi=dpi, paper=paper)
        target = out_dir / f"page_{index:03d}.{fmt}"
        if fmt == "jpg":
            img.save(target, format="JPEG", quality=quality, optimize=True, dpi=(dpi, dpi))
        else:
            img.save(target, format="PNG", dpi=(dpi, dpi))
        paths.append(str(target))
        if progress is not None:
            progress(index, total)
    return paths


def full_frame_corners() -> np.ndarray:
    """整图四角（检测失败时的兜底）。"""
    return np.array(
        [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]], dtype=np.float32
    )


__all__ = [
    "FILTERS",
    "PAPER_SIZES_MM",
    "SIGNATURE_ANCHORS",
    "ScanPage",
    "Signature",
    "apply_signature",
    "detect_document_corners",
    "enhance_document",
    "export_scan_images",
    "export_scan_pdf",
    "full_frame_corners",
    "load_image",
    "order_corners",
    "render_page",
    "rotate_rgb",
    "warp_document",
]
