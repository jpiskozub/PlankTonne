# Service unit tests

import cv2
import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from app.services.geometry import smooth_contour, select_largest_contour_in_roi
from app.services.aruco import calibrate_from_aruco
from app.core.exceptions import ArucoNotFoundError, ContourNotFoundError


def make_aruco_image(marker_id: int = 0, marker_size_px: int = 100, image_size: int = 400) -> np.ndarray:
    """Synthesize a grayscale image containing one DICT_6X6_250 ArUco marker."""
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_250)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, marker_size_px)
    image = np.ones((image_size, image_size), dtype=np.uint8) * 200
    offset = (image_size - marker_size_px) // 2
    image[offset:offset + marker_size_px, offset:offset + marker_size_px] = marker_img
    return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)


# --- geometry ---

def test_smooth_contour_preserves_shape():
    contour = np.array([[[0, 0]], [[10, 0]], [[10, 10]], [[0, 10]]], dtype=np.int32)
    smoothed = smooth_contour(contour, window_length=3)
    assert smoothed.shape == contour.shape
    assert smoothed.dtype == np.int32


def test_smooth_contour_too_short_returns_original():
    contour = np.array([[[0, 0]], [[5, 0]], [[5, 5]]], dtype=np.int32)
    result = smooth_contour(contour, window_length=11)
    np.testing.assert_array_equal(result, contour)


def test_select_largest_contour_in_roi_basic():
    mask = np.zeros((200, 200), dtype=np.uint8)
    cv2.rectangle(mask, (50, 50), (150, 150), 255, -1)
    roi = np.array([[0, 0], [200, 0], [200, 200], [0, 200]])

    contour, area_px, perimeter_px = select_largest_contour_in_roi(mask, roi)

    assert area_px > 0
    assert perimeter_px > 0
    assert contour is not None


def test_select_largest_contour_picks_biggest():
    mask = np.zeros((300, 300), dtype=np.uint8)
    cv2.rectangle(mask, (10, 10), (30, 30), 255, -1)   # small: 400 px²
    cv2.rectangle(mask, (100, 100), (200, 200), 255, -1)  # large: 10000 px²
    roi = np.array([[0, 0], [300, 0], [300, 300], [0, 300]])

    contour, area_px, _ = select_largest_contour_in_roi(mask, roi)

    assert area_px > 400


def test_select_largest_contour_empty_mask_raises():
    mask = np.zeros((100, 100), dtype=np.uint8)
    roi = np.array([[0, 0], [100, 0], [100, 100], [0, 100]])

    with pytest.raises(ContourNotFoundError):
        select_largest_contour_in_roi(mask, roi)


# --- aruco ---

def test_calibrate_from_aruco_detects_scale():
    marker_size_mm = 100.0
    marker_size_px = 100
    image = make_aruco_image(marker_size_px=marker_size_px)

    pixels_per_mm, homography = calibrate_from_aruco(image, marker_size_mm)

    # With 100px marker = 100mm, scale should be ~1.0 px/mm
    assert abs(pixels_per_mm - 1.0) < 0.2
    assert homography is not None
    assert homography.shape == (3, 3)


def test_calibrate_from_aruco_no_marker_raises():
    image = np.ones((200, 200, 3), dtype=np.uint8) * 128

    with pytest.raises(ArucoNotFoundError):
        calibrate_from_aruco(image, 100.0)


# --- segmentation ---

def test_segment_in_roi_returns_correct_shape():
    image = np.zeros((200, 200, 3), dtype=np.uint8)
    cv2.rectangle(image, (50, 50), (150, 150), (100, 150, 200), -1)
    roi = np.array([[40, 40], [160, 40], [160, 160], [40, 160]])

    def fake_remove(crop, session=None):
        h, w = crop.shape[:2]
        result = np.zeros((h, w, 4), dtype=np.uint8)
        result[..., 3] = 255
        return result

    with patch("rembg.remove", side_effect=fake_remove):
        with patch("app.services.segmentation.get_rembg_session", return_value=MagicMock()):
            from app.services.segmentation import segment_in_roi
            mask = segment_in_roi(image, roi)

    assert mask.shape == image.shape[:2]
    assert mask.dtype == np.uint8
    assert mask.max() == 255
