# Main pipeline orchestration service

import asyncio
import cv2
import numpy as np

from app.api.schemas import MeasureBoardsRequest, MeasureBoardsResponse, BoardResult
from app.core.exceptions import ArucoNotFoundError, ContourNotFoundError
from app.core.logging import log
from app.services.aruco import calibrate_from_aruco
from app.services.segmentation import segment_in_roi
from app.services.geometry import select_largest_contour_in_roi


async def measure_boards(request: MeasureBoardsRequest) -> MeasureBoardsResponse:
    """
    Main pipeline: measure board areas from image and ROIs.

    Args:
        request: Measurement request

    Returns:
        Measurement response with board areas and resin volume
    """
    nparr = np.frombuffer(request.image_data, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Invalid image data")

    log.info("Image decoded", shape=str(image.shape))

    marker_size_mm = request.rois[0].marker_size_mm if request.rois else 100.0
    pixels_per_mm, _ = calibrate_from_aruco(image, marker_size_mm) if request.rois else (1.0, None)

    board_results = []
    total_board_area = 0.0

    for i, roi in enumerate(request.rois):
        try:
            roi_points = np.array([[p.x, p.y] for p in roi.polygon])

            mask = await asyncio.to_thread(segment_in_roi, image, roi_points)
            contour, area_pixels, perimeter_pixels = await asyncio.to_thread(
                select_largest_contour_in_roi, mask, roi_points
            )

            area_mm2 = area_pixels / (pixels_per_mm ** 2)
            perimeter_mm = perimeter_pixels / pixels_per_mm

            board_results.append(BoardResult(
                area_mm2=area_mm2,
                perimeter_mm=perimeter_mm,
                roi_index=i,
            ))
            total_board_area += area_mm2

            log.info("Board measured", roi_index=i, area_mm2=area_mm2, perimeter_mm=perimeter_mm)

        except (ArucoNotFoundError, ContourNotFoundError) as e:
            log.error("Domain error processing ROI", roi_index=i, error=str(e))
            continue
        except Exception as e:
            log.error("Unexpected error processing ROI", roi_index=i, error=str(e))
            continue

    form_area_mm2 = request.form_length_mm * request.form_width_mm
    resin_area_mm2 = form_area_mm2 - total_board_area
    resin_volume_mm3 = resin_area_mm2 * request.form_depth_mm
    resin_volume_liters = resin_volume_mm3 / 1_000_000 * 1.10

    response = MeasureBoardsResponse(
        boards=board_results,
        total_board_area_mm2=total_board_area,
        resin_volume_mm3=resin_volume_mm3,
        resin_volume_liters=resin_volume_liters,
    )

    log.info("Pipeline completed", board_count=len(board_results), resin_volume_liters=resin_volume_liters)

    return response