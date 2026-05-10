# ArUco marker detection and calibration service

import cv2
import numpy as np
from typing import Tuple

from app.core.exceptions import ArucoNotFoundError
from app.core.logging import log

_ARUCO_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

_DETECTION_STRATEGIES = [
    # (label, adaptiveThreshWinSizeMax, errorCorrectionRate, use_clahe, invert)
    ("default",          23,  0.6, False, False),
    ("large_window",     53,  0.6, False, False),
    ("high_correction",  23,  0.9, False, False),
    ("large+correction", 53,  0.9, False, False),
    ("clahe",            23,  0.6, True,  False),
    ("clahe+large",      53,  0.9, True,  False),
    ("inverted",         53,  0.9, False, True),
]


def _make_params(win_max: int, error_rate: float) -> cv2.aruco.DetectorParameters:
    p = cv2.aruco.DetectorParameters()
    p.adaptiveThreshWinSizeMin = 3
    p.adaptiveThreshWinSizeMax = win_max
    p.adaptiveThreshWinSizeStep = 10
    p.errorCorrectionRate = error_rate
    return p


def _detect_with_strategy(gray: np.ndarray, win_max: int, error_rate: float,
                           use_clahe: bool, invert: bool):
    img = gray.copy()
    if use_clahe:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe.apply(img)
    if invert:
        img = cv2.bitwise_not(img)
    params = _make_params(win_max, error_rate)
    detector = cv2.aruco.ArucoDetector(_ARUCO_DICT, params)
    return detector.detectMarkers(img)


def calibrate_from_aruco(
    image: np.ndarray,
    marker_size_mm: float,
) -> Tuple[float, np.ndarray]:
    """
    Detect ArUco marker (DICT_6X6_250) and calculate pixels-to-mm scale.
    Tries multiple detection strategies to handle varying image conditions.

    Args:
        image: BGR image array
        marker_size_mm: Physical size of marker side in mm

    Returns:
        Tuple of (pixels_per_mm, homography_matrix)

    Raises:
        ArucoNotFoundError: If marker not found with any strategy
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    corners, ids = None, None
    for label, win_max, error_rate, use_clahe, invert in _DETECTION_STRATEGIES:
        c, i, _ = _detect_with_strategy(gray, win_max, error_rate, use_clahe, invert)
        if i is not None and len(i) > 0:
            corners, ids = c, i
            log.info("ArUco detected", strategy=label, marker_id=int(ids[0][0]))
            break

    if ids is None:
        raise ArucoNotFoundError("No ArUco markers found in image (tried all strategies)")

    marker_corners = corners[0][0]  # shape: (4, 2)

    side_lengths = [
        np.linalg.norm(marker_corners[i] - marker_corners[(i + 1) % 4])
        for i in range(4)
    ]
    pixels_per_mm = float(np.mean(side_lengths)) / marker_size_mm

    marker_points = np.array([
        [0, 0],
        [marker_size_mm, 0],
        [marker_size_mm, marker_size_mm],
        [0, marker_size_mm],
    ], dtype=np.float32)
    homography, _ = cv2.findHomography(marker_corners, marker_points)

    log.info("ArUco calibration completed", pixels_per_mm=round(pixels_per_mm, 3),
             marker_id=int(ids[0][0]))

    return pixels_per_mm, homography
