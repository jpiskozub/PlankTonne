# Schema validation tests

import pytest
from pydantic import ValidationError

from app.api.schemas import MeasureBoardsRequest, Point, RoiInput


def test_measure_boards_request_rejects_large_image():
    """The request should reject image data larger than the allowed maximum."""
    large_image = b"0" * (15 * 1024 * 1024 + 1)

    with pytest.raises(ValidationError):
        MeasureBoardsRequest(
            image_data=large_image,
            form_length_mm=1000.0,
            form_width_mm=600.0,
            form_depth_mm=50.0,
            rois=[],
        )


def test_measure_boards_request_accepts_empty_rois():
    """The request should allow an empty ROI list and still validate."""
    request = MeasureBoardsRequest(
        image_data=b"test",
        form_length_mm=1000.0,
        form_width_mm=600.0,
        form_depth_mm=50.0,
        rois=[],
    )

    assert request.rois == []
    assert request.form_length_mm == 1000.0


def test_roi_input_validation():
    """ROI input should enforce at least 3 points and positive marker size."""
    with pytest.raises(ValidationError):
        RoiInput(
            polygon=[Point(x=0.0, y=0.0), Point(x=1.0, y=1.0)],
            marker_size_mm=50.0,
        )

    with pytest.raises(ValidationError):
        RoiInput(
            polygon=[Point(x=0.0, y=0.0), Point(x=1.0, y=0.0), Point(x=0.0, y=1.0)],
            marker_size_mm=0.0,
        )
