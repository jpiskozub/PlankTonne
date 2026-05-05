# Main pipeline orchestration service

import asyncio
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np
from typing import List

from app.api.schemas import MeasureBoardsRequest, MeasureBoardsResponse, BoardResult
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
    # Decode image
    nparr = np.frombuffer(request.image_data, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Invalid image data")

    log.info("Image decoded", shape=image.shape)

    # Process each ROI
    board_results = []
    total_board_area = 0.0

    for i, roi in enumerate(request.rois):
        try:
            # Convert ROI points to numpy array
            roi_points = np.array([[p.x, p.y] for p in roi.polygon])

            # Calibrate scale from ArUco marker
            pixels_per_mm, _ = calibrate_from_aruco(image, roi.marker_size_mm)

            # Segment in ROI (CPU-bound, run in thread pool)
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                mask = await loop.run_in_executor(
                    executor, segment_in_roi, image, roi_points
                )

            # Find contour and calculate metrics (CPU-bound)
            contour, area_pixels, perimeter_pixels = await loop.run_in_executor(
                executor, select_largest_contour_in_roi, mask, roi_points
            )

            # Convert to mm
            area_mm2 = area_pixels / (pixels_per_mm ** 2)
            perimeter_mm = perimeter_pixels / pixels_per_mm

            board_result = BoardResult(
                area_mm2=area_mm2,
                perimeter_mm=perimeter_mm,
                roi_index=i,
            )
            board_results.append(board_result)
            total_board_area += area_mm2

            log.info(
                f"Board {i} measured",
                area_mm2=area_mm2,
                perimeter_mm=perimeter_mm,
            )

        except Exception as e:
            log.error(f"Failed to process ROI {i}", error=str(e))
            # Continue with other ROIs
            continue

    # Calculate resin volume
    form_area_mm2 = request.form_length_mm * request.form_width_mm
    resin_area_mm2 = form_area_mm2 - total_board_area
    resin_volume_mm3 = resin_area_mm2 * request.form_depth_mm
    resin_volume_liters = resin_volume_mm3 / 1_000_000 * 1.10  # 10% reserve

    response = MeasureBoardsResponse(
        boards=board_results,
        total_board_area_mm2=total_board_area,
        resin_volume_mm3=resin_volume_mm3,
        resin_volume_liters=resin_volume_liters,
    )

    log.info(
        "Pipeline completed",
        board_count=len(board_results),
        resin_volume_liters=resin_volume_liters,
    )

    return response