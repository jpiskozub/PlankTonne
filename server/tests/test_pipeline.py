# Pipeline integration tests

import pytest
import numpy as np
from app.api.schemas import MeasureBoardsRequest, Point, RoiInput
from app.services.pipeline import measure_boards


@pytest.mark.asyncio
async def test_measure_boards_empty_image():
    """Test pipeline with invalid image."""
    request = MeasureBoardsRequest(
        image_data=b"invalid",
        form_length_mm=1000.0,
        form_width_mm=600.0,
        form_depth_mm=50.0,
        rois=[],
    )

    with pytest.raises(ValueError, match="Invalid image data"):
        await measure_boards(request)


@pytest.mark.asyncio
async def test_measure_boards_no_rois():
    """Test pipeline with no ROIs."""
    # Create minimal valid image (1x1 pixel)
    image_data = np.zeros((1, 1, 3), dtype=np.uint8)
    _, encoded = cv2.imencode('.png', image_data)

    request = MeasureBoardsRequest(
        image_data=encoded.tobytes(),
        form_length_mm=1000.0,
        form_width_mm=600.0,
        form_depth_mm=50.0,
        rois=[],
    )

    result = await measure_boards(request)
    assert result.boards == []
    assert result.total_board_area_mm2 == 0.0
    assert result.resin_volume_mm3 == 1000.0 * 600.0 * 50.0
    assert result.resin_volume_liters == result.resin_volume_mm3 / 1_000_000 * 1.10