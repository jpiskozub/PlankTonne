"""
Manual integration test — run this while the server is running.

Usage:
    uv run python test_manual.py
    uv run python test_manual.py --image photo.jpg --marker-size 50
    uv run python test_manual.py --url http://192.168.1.x:8000
"""

import argparse
import json
import sys

import cv2
import numpy as np
import requests


def make_test_image(width: int = 800, height: int = 600) -> tuple[bytes, np.ndarray]:
    """Generate synthetic image: white background + ArUco marker + 'board' rectangle."""
    image = np.ones((height, width, 3), dtype=np.uint8) * 240

    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_5X5_250)
    marker = cv2.aruco.generateImageMarker(aruco_dict, 0, 100)
    image[20:120, 20:120] = cv2.cvtColor(marker, cv2.COLOR_GRAY2BGR)

    cv2.rectangle(image, (200, 150), (600, 450), (60, 80, 100), -1)
    noise = np.random.randint(-20, 20, (300, 400, 3), dtype=np.int16)
    board_region = image[150:450, 200:600].astype(np.int16) + noise
    image[150:450, 200:600] = np.clip(board_region, 0, 255).astype(np.uint8)

    _, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    return encoded.tobytes(), image


def select_roi_interactive(image_bgr: np.ndarray) -> list[dict]:
    """Show image, let user draw a rectangle ROI. Returns polygon list."""
    print("  Zaznacz ROI wokół deski (przeciągnij prostokąt), potem ENTER lub SPACJA.")
    print("  Możesz zaznaczyć kilka ROI — po każdym ENTER, po ostatnim ESC lub 'q'.")

    display = image_bgr.copy()
    h, w = display.shape[:2]
    scale = min(1.0, 1200 / w, 800 / h)
    if scale < 1.0:
        display = cv2.resize(display, (int(w * scale), int(h * scale)))

    polygons = []
    while True:
        x, y, rw, rh = cv2.selectROI("Zaznacz ROI — ENTER=OK, ESC=koniec", display, fromCenter=False)
        cv2.destroyAllWindows()
        if rw == 0 or rh == 0:
            break
        # scale back to original pixel coords
        x1, y1 = int(x / scale), int(y / scale)
        x2, y2 = int((x + rw) / scale), int((y + rh) / scale)
        polygon = [
            {"x": x1, "y": y1},
            {"x": x2, "y": y1},
            {"x": x2, "y": y2},
            {"x": x1, "y": y2},
        ]
        polygons.append(polygon)
        print(f"  ROI #{len(polygons)}: ({x1},{y1}) → ({x2},{y2})")
        # draw selected roi on display for next iteration
        cv2.rectangle(display, (x, y), (x + rw, y + rh), (0, 255, 0), 2)
        cv2.putText(display, f"#{len(polygons)}", (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    return polygons



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--image", default=None, help="Ścieżka do zdjęcia (domyślnie: syntetyczne)")
    parser.add_argument("--marker-size", type=float, default=100.0,
                        help="Fizyczny rozmiar markera ArUco w mm (domyślnie: 50)")
    parser.add_argument("--form-length", type=float, default=500.0, help="Długość formy w mm")
    parser.add_argument("--form-width", type=float, default=400.0, help="Szerokość formy w mm")
    parser.add_argument("--form-depth", type=float, default=30.0, help="Głębokość formy w mm")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    if args.image:
        print(f"Wczytuję zdjęcie: {args.image}")
        image_bgr = cv2.imread(args.image)
        if image_bgr is None:
            print(f"  ERROR: nie można otworzyć pliku {args.image}")
            sys.exit(1)
        _, encoded = cv2.imencode(".jpg", image_bgr, [cv2.IMWRITE_JPEG_QUALITY, 95])
        image_bytes = encoded.tobytes()
        print(f"  Rozmiar: {image_bgr.shape[1]}×{image_bgr.shape[0]} px, {len(image_bytes)/1024:.1f} KB")

        polygons = select_roi_interactive(image_bgr)
        if not polygons:
            print("  Nie zaznaczono żadnego ROI — koniec.")
            sys.exit(0)

        rois = [{"polygon": p, "marker_size_mm": args.marker_size} for p in polygons]
    else:
        print("Generating synthetic test image...")
        image_bytes, image_bgr = make_test_image()
        cv2.imwrite("test_manual_image.jpg", image_bgr)
        print(f"  Size: {len(image_bytes) / 1024:.1f} KB")
        print(f"  Saved: test_manual_image.jpg")
        rois = [
            {
                "polygon": [
                    {"x": 190, "y": 140},
                    {"x": 610, "y": 140},
                    {"x": 610, "y": 460},
                    {"x": 190, "y": 460},
                ],
                "marker_size_mm": 50.0,
            }
        ]

    # --- health check ---
    print(f"\nConnecting to {base_url} ...")
    try:
        r = requests.get(f"{base_url}/health", timeout=5)
        r.raise_for_status()
        print(f"  /health → {r.json()}")
    except Exception as e:
        print(f"  ERROR: server not reachable — {e}")
        print("  Start server first: uv run uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    print(f"\nSending to /v1/measure-boards ...")
    print(f"  ROI: {len(rois)} szt., marker: {args.marker_size} mm")
    print(f"  Forma: {args.form_length}×{args.form_width}×{args.form_depth} mm")
    try:
        r = requests.post(
            f"{base_url}/v1/measure-boards",
            files={"image": ("test.jpg", image_bytes, "image/jpeg")},
            data={
                "form_length_mm": args.form_length,
                "form_width_mm": args.form_width,
                "form_depth_mm": args.form_depth,
                "rois": json.dumps(rois),
            },
            timeout=120,
        )
    except requests.exceptions.Timeout:
        print("  Timeout — rembg model might still be loading, wait and retry")
        sys.exit(1)

    if r.status_code != 200:
        print(f"  ERROR {r.status_code}: {r.text}")
        sys.exit(1)

    result = r.json()
    print(f"\n{'─'*40}")
    print(f"  Boards detected:      {len(result['boards'])}")
    for b in result["boards"]:
        print(f"    ROI #{b['roi_index']}: area={b['area_mm2']:.0f} mm²  perimeter={b['perimeter_mm']:.0f} mm")
    print(f"  Total board area:     {result['total_board_area_mm2']:.0f} mm²")
    print(f"  Resin volume:         {result['resin_volume_mm3']:.0f} mm³")
    print(f"  Resin (liters +10%):  {result['resin_volume_liters']:.3f} L")
    print(f"{'─'*40}")


if __name__ == "__main__":
    main()
