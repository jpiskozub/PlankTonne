# API routes

from typing import List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse

from app.api.schemas import (
    MeasureBoardsRequest,
    MeasureBoardsResponse,
    RoiInput,
)
from app.core.exceptions import PlankTonneError
from app.core.logging import log
from app.services.pipeline import measure_boards

router = APIRouter()


def parse_rois_from_form(rois_data: str) -> List[RoiInput]:
    """Parse ROIs from JSON string in form data."""
    import json
    try:
        rois_dict = json.loads(rois_data)
        return [RoiInput(**roi) for roi in rois_dict]
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid ROIs format: {e}")


@router.post("/measure-boards", response_model=MeasureBoardsResponse)
async def measure_boards_endpoint(
    image: UploadFile = File(...),
    form_length_mm: float = Form(..., gt=0),
    form_width_mm: float = Form(..., gt=0),
    form_depth_mm: float = Form(..., gt=0),
    rois: str = Form(...),
) -> MeasureBoardsResponse:
    """
    Measure board areas from image and ROIs.

    - **image**: Image file containing the form with ArUco marker
    - **form_length_mm**: Length of the form in mm
    - **form_width_mm**: Width of the form in mm
    - **form_depth_mm**: Depth/resin height in mm
    - **rois**: JSON string with list of ROIs
    """
    try:
        # Read image data
        image_data = await image.read()

        # Parse ROIs
        rois_list = parse_rois_from_form(rois)

        # Create request object
        request = MeasureBoardsRequest(
            image_data=image_data,
            form_length_mm=form_length_mm,
            form_width_mm=form_width_mm,
            form_depth_mm=form_depth_mm,
            rois=rois_list,
        )

        # Process request
        log.info("Processing measure-boards request", roi_count=len(rois_list))
        result = await measure_boards(request)

        log.info(
            "Measure-boards completed",
            board_count=len(result.boards),
            total_area=result.total_board_area_mm2,
            volume_liters=result.resin_volume_liters,
        )

        return result

    except PlankTonneError as e:
        log.error("Application error", error=str(e), details=e.details)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("Unexpected error", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")