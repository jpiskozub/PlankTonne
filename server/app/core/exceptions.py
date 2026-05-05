# Custom exceptions for the application

from typing import Any, Dict, Optional


class PlankTonneError(Exception):
    """Base exception for PlankTonne application."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.details = details or {}


class ArucoNotFoundError(PlankTonneError):
    """Raised when ArUco marker is not found in the image."""
    pass


class ContourNotFoundError(PlankTonneError):
    """Raised when no contours are found in the ROI."""
    pass


class InvalidRoiError(PlankTonneError):
    """Raised when ROI is invalid."""
    pass


class ImageProcessingError(PlankTonneError):
    """Raised when image processing fails."""
    pass