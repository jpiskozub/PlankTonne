# Image segmentation service using Rembg

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import log


_rembg_session = None


def get_rembg_session():
    global _rembg_session
    if _rembg_session is None:
        from rembg import new_session
        log.info("Creating Rembg session", model=settings.rembg_model)
        _rembg_session = new_session(settings.rembg_model)
    return _rembg_session


def segment_in_roi(
    image_bgr: np.ndarray,
    roi_polygon: np.ndarray,
) -> np.ndarray:
    """
    Segment object in ROI using Rembg.

    Args:
        image_bgr: Full BGR image
        roi_polygon: ROI polygon as (N, 2) array of points in image pixel coords

    Returns:
        Binary mask (same size as image_bgr) of segmented object clipped to ROI
    """
    from rembg import remove

    roi_mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
    cv2.fillPoly(roi_mask, [roi_polygon.astype(np.int32)], 255)

    x, y, w, h = cv2.boundingRect(roi_polygon.astype(np.int32))
    margin = int(max(w, h) * 0.10)
    x1 = max(0, x - margin)
    y1 = max(0, y - margin)
    x2 = min(image_bgr.shape[1], x + w + margin)
    y2 = min(image_bgr.shape[0], y + h + margin)

    roi_crop = image_bgr[y1:y2, x1:x2]

    session = get_rembg_session()
    segmented = remove(roi_crop, session=session)

    if segmented.shape[2] == 4:
        alpha = segmented[:, :, 3]
        _, binary_mask = cv2.threshold(alpha, 127, 255, cv2.THRESH_BINARY)
    else:
        gray = cv2.cvtColor(segmented, cv2.COLOR_RGB2GRAY)
        _, binary_mask = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    full_mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = binary_mask
    full_mask = cv2.bitwise_and(full_mask, roi_mask)

    roi_area_px = int(cv2.contourArea(roi_polygon.reshape(-1, 1, 2).astype(np.float32)))
    log.info("Segmentation completed", roi_area_px=roi_area_px)

    return full_mask