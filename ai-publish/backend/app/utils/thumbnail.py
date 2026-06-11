"""图片缩略图生成（列表预览用）。"""

from __future__ import annotations

from pathlib import Path


def generate_image_thumbnail(source_path: str, storage) -> str | None:
    path = Path(source_path)
    if not path.exists():
        return None
    try:
        import cv2

        image = cv2.imread(str(path))
        if image is None:
            return None
        height, width = image.shape[:2]
        max_dim = 240
        scale = min(1.0, max_dim / max(height, width, 1))
        if scale < 1.0:
            image = cv2.resize(image, (int(width * scale), int(height * scale)))
        ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            return None
        thumb_path, _ = storage.save_bytes(encoded.tobytes(), suffix="_thumb.jpg")
        return thumb_path
    except Exception:
        return None
