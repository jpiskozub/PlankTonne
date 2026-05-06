# Geometry and contour processing service

import cv2
import numpy as np
from scipy.signal import savgol_filter
from typing import Tuple, Optional

from app.core.exceptions import ContourNotFoundError
from app.core.logging import log


def smooth_contour(contour: np.ndarray, window_length: int = 11) -> np.ndarray:
    """
    Smooth contour using Savitzky-Golay filter.

    Args:
        contour: Contour points as (N, 1, 2) array
        window_length: Filter window length (must be odd)

    Returns:
        Smoothed contour
    """
    if len(contour) < window_length:
        return contour

    # Reshape to (N, 2)
    points = contour.reshape(-1, 2)

    # Determine polyorder safely for short curves
    polyorder = min(3, window_length - 1)
    smoothed_x = savgol_filter(points[:, 0], window_length, polyorder)
    smoothed_y = savgol_filter(points[:, 1], window_length, polyorder)

    # Reshape back
    smoothed = np.column_stack([smoothed_x, smoothed_y])
    return smoothed.reshape(-1, 1, 2).astype(np.int32)


def select_largest_contour_in_roi(
    binary_mask: np.ndarray,
    roi_polygon: np.ndarray,
) -> Tuple[np.ndarray, float, float]:
    """
    Find and smooth the largest contour in ROI.

    Args:
        binary_mask: Binary mask from segmentation
        roi_polygon: ROI polygon for area calculation

    Returns:
        Tuple of (smoothed_contour, area_pixels, perimeter_pixels)

    Raises:
        ContourNotFoundError: If no contours found
    """
    # Find contours
    contours, _ = cv2.findContours(
        binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        raise ContourNotFoundError("No contours found in segmented mask")

    # Find largest contour by area
    largest_contour = max(contours, key=cv2.contourArea)

    # Smooth contour
    smoothed = smooth_contour(largest_contour)

    # Calculate metrics
    area_pixels = cv2.contourArea(smoothed)
    perimeter_pixels = cv2.arcLength(smoothed, True)

    log.info(
        "Contour selected",
        area_pixels=area_pixels,
        perimeter_pixels=perimeter_pixels,
        contour_points=len(smoothed),
    )

    return smoothed, area_pixels, perimeter_pixels