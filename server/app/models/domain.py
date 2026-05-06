# Domain dataclasses for business logic

from dataclasses import dataclass
from typing import List, Tuple
import numpy as np


@dataclass
class Roi:
    """Region of Interest for board measurement."""
    polygon: List[Tuple[float, float]]  # List of (x, y) points
    marker_size_mm: float


@dataclass
class BoardMeasurement:
    """Measurement result for a single board."""
    area_mm2: float
    perimeter_mm: float
    contour: np.ndarray  # Smoothed contour points


@dataclass
class CalibrationResult:
    """Result of ArUco calibration."""
    pixels_per_mm: float
    homography: np.ndarray