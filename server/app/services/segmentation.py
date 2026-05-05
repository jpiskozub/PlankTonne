# Image segmentation service using Rembg

import numpy as np
from typing import Tuple
from rembg import remove, new_session

from app.core.config import settings
from app.core.logging import log


# Global session for model reuse
_rembg_session = None


def get_rembg_session():
    """Get or create Rembg session."""
    global _rembg_session
    if _rembg_session is None:
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
        roi_polygon: ROI polygon as (N, 2) array of points

    Returns:
        Binary mask of segmented object within ROI
    """
    # Create mask from polygon
    roi_mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
    cv2.fillPoly(roi_mask, [roi_polygon.astype(np.int32)], 255)

    # Add margin to ROI for better segmentation
    margin = 10  # pixels
    roi_rect = cv2.boundingRect(roi_polygon.astype(np.int32))
    x, y, w, h = roi_rect
    x1, y1 = max(0, x - margin), max(0, y - margin)
    x2, y2 = min(image_bgr.shape[1], x + w + margin), min(image_bgr.shape[0], y + h + margin)

    # Crop image with margin
    roi_crop = image_bgr[y1:y2, x1:x2]

    # Segment using Rembg
    session = get_rembg_session()
    segmented = remove(roi_crop, session=session)

    # Convert to grayscale mask
    if segmented.shape[2] == 4:  # RGBA
        mask = cv2.cvtColor(segmented, cv2.COLOR_RGBA2GRAY)
    else:  # RGB
        mask = cv2.cvtColor(segmented, cv2.COLOR_RGB2GRAY)

    # Threshold to binary
    _, binary_mask = cv2.threshold(mask, 127, 255, cv2.THRESH_BINARY)

    # Create full-size mask
    full_mask = np.zeros(image_bgr.shape[:2], dtype=np.uint8)
    full_mask[y1:y2, x1:x2] = binary_mask

    # Apply original ROI mask
    full_mask = cv2.bitwise_and(full_mask, roi_mask)

    log.info("Segmentation completed", roi_area=cv2.contourArea(roi_polygon))

    return full_mask