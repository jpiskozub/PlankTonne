# Service unit tests

import numpy as np
import pytest
from app.services.geometry import smooth_contour


def test_smooth_contour():
    """Test contour smoothing."""
    # Create simple square contour
    contour = np.array([
        [[0, 0]],
        [[10, 0]],
        [[10, 10]],
        [[0, 10]]
    ], dtype=np.int32)

    smoothed = smooth_contour(contour, window_length=3)

    # Should preserve shape
    assert smoothed.shape == contour.shape
    assert smoothed.dtype == np.int32