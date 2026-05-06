# Pydantic schemas for API requests and responses

from typing import List, Tuple

from pydantic import BaseModel, Field, validator


class Point(BaseModel):
    """A 2D point."""
    x: float
    y: float


class RoiInput(BaseModel):
    """Input for a single ROI."""
    polygon: List[Point] = Field(..., min_items=3, max_items=100)
    marker_size_mm: float = Field(..., gt=0, le=1000)


class MeasureBoardsRequest(BaseModel):
    """Request to measure board areas."""
    image_data: bytes
    form_length_mm: float = Field(..., gt=0)
    form_width_mm: float = Field(..., gt=0)
    form_depth_mm: float = Field(..., gt=0)
    rois: List[RoiInput] = Field(..., min_items=1, max_items=20)

    @validator("image_data")
    def validate_image_size(cls, v):
        max_size = 15 * 1024 * 1024  # 15MB
        if len(v) > max_size:
            raise ValueError("Image too large (max 15MB)")
        return v


class BoardResult(BaseModel):
    """Result for a single board measurement."""
    area_mm2: float
    perimeter_mm: float
    roi_index: int


class MeasureBoardsResponse(BaseModel):
    """Response from measure-boards endpoint."""
    boards: List[BoardResult]
    total_board_area_mm2: float
    resin_volume_mm3: float
    resin_volume_liters: float