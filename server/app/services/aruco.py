# ArUco marker detection and calibration service

import cv2
import numpy as np
from typing import Tuple, Optional

from app.core.exceptions import ArucoNotFoundError
from app.core.logging import log


def calibrate_from_aruco(
    image: np.ndarray,
    marker_size_mm: float,
) -> Tuple[float, np.ndarray]:
    """
    Detect ArUco marker and calculate pixels-to-mm scale.

    Args:
        image: BGR image array
        marker_size_mm: Physical size of marker side in mm

    Returns:
        Tuple of (pixels_per_mm, homography_matrix)

    Raises:
        ArucoNotFoundError: If marker not found
    """
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # Detect ArUco markers
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)
    parameters = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    corners, ids, rejected = detector.detectMarkers(gray)

    if ids is None or len(ids) == 0:
        raise ArucoNotFoundError("No ArUco markers found in image")

    # Use first detected marker
    marker_corners = corners[0][0]  # Shape: (4, 2)

    # Calculate pixel distance between corners
    # Assuming square marker, distance between opposite corners
    dist_px = np.linalg.norm(marker_corners[0] - marker_corners[2])

    # Calculate pixels per mm
    pixels_per_mm = dist_px / marker_size_mm

    # Calculate homography for perspective correction (optional)
    # This could be used later for undistorting the image
    marker_points = np.array([
        [0, 0],           # top-left
        [marker_size_mm, 0],    # top-right
        [marker_size_mm, marker_size_mm],  # bottom-right
        [0, marker_size_mm]     # bottom-left
    ], dtype=np.float32)

    homography, _ = cv2.findHomography(marker_corners, marker_points)

    log.info(
        "ArUco calibration completed",
        pixels_per_mm=pixels_per_mm,
        marker_id=int(ids[0][0]),
    )

    return pixels_per_mm, homography