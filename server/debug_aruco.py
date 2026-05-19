"""
Diagnoza wykrywania markera ArUco.

Usage:
    uv run python debug_aruco.py --image foto.jpg
"""

import argparse
import sys
import cv2
import numpy as np


ARUCO_DICT = cv2.aruco.DICT_5X5_250


def make_params(win_min=3, win_max=23, win_step=10, error_rate=0.6) -> cv2.aruco.DetectorParameters:
    p = cv2.aruco.DetectorParameters()
    p.adaptiveThreshWinSizeMin = win_min
    p.adaptiveThreshWinSizeMax = win_max
    p.adaptiveThreshWinSizeStep = win_step
    p.errorCorrectionRate = error_rate
    return p


def detect(gray: np.ndarray, params: cv2.aruco.DetectorParameters):
    d = cv2.aruco.ArucoDetector(cv2.aruco.getPredefinedDictionary(ARUCO_DICT), params)
    return d.detectMarkers(gray)


def try_all(gray: np.ndarray, label: str):
    attempts = [
        ("domyślne",          make_params()),
        ("duże okno",         make_params(win_min=3, win_max=53, win_step=10)),
        ("wysoka korekcja",   make_params(error_rate=0.9)),
        ("duże okno + korekcja", make_params(win_min=3, win_max=53, error_rate=0.9)),
    ]
    for name, params in attempts:
        corners, ids, rejected = detect(gray, params)
        found = ids is not None and len(ids) > 0
        tag = "✓ ZNALEZIONO" if found else "✗ nie"
        marker_id = f" id={ids[0][0]}" if found else f" (odrzuconych={len(rejected)})"
        print(f"  [{label} / {name}] {tag}{marker_id}")
        if found:
            return corners, ids, rejected
    return detect(gray, make_params()), None, None  # zwróć rejected do wizualizacji


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", required=True)
    args = parser.parse_args()

    image = cv2.imread(args.image)
    if image is None:
        print(f"ERROR: nie można otworzyć {args.image}")
        sys.exit(1)

    h, w = image.shape[:2]
    print(f"\nObraz: {w}×{h} px")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    scale = min(1.0, 1200 / w)
    small = cv2.resize(gray, (int(w * scale), int(h * scale)))

    print("\n--- Próby wykrycia markera ---")

    # 1. Oryginalny obraz
    corners, ids, rejected = try_all(gray, "oryginał")
    found = ids is not None

    # 2. Wyrównanie histogramu (poprawia kontrast)
    if not found:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_clahe = clahe.apply(gray)
        corners, ids, rejected = try_all(gray_clahe, "CLAHE")
        found = ids is not None

    # 3. Obraz odwrócony (biały marker na czarnym tle)
    if not found:
        corners, ids, rejected = try_all(cv2.bitwise_not(gray), "odwrócony")
        found = ids is not None

    # 4. Przeskalowany do 1200px
    if not found:
        corners_s, ids_s, rejected_s = try_all(small, f"skala {scale:.2f}")
        if ids_s is not None:
            # przeskaluj współrzędne z powrotem
            corners = [[c / scale for c in corners_s[0]]] if corners_s else []
            ids, rejected = ids_s, rejected_s
            found = True

    # Wizualizacja
    vis = cv2.cvtColor(small, cv2.COLOR_GRAY2BGR)
    if found and corners:
        scaled_corners = [[np.array(c) * scale for c in corners[0]]]
        # przelicz do small
        vis_corners = [np.array([[p * scale for p in corners[0][0]]], dtype=np.float32)]
        cv2.aruco.drawDetectedMarkers(vis, vis_corners, ids)
        mc = corners[0][0]
        side_px = float(np.mean([
            np.linalg.norm(np.array(mc[i]) - np.array(mc[(i + 1) % 4]))
            for i in range(4)
        ]))
        print(f"\nBok markera: {side_px:.1f} px (w oryginale)")
        print(f"Przy marker_size=50mm → {side_px/50:.2f} px/mm")
    else:
        if rejected:
            rej_small = [np.array(r * scale, dtype=np.float32) for r in rejected]
            cv2.aruco.drawDetectedMarkers(vis, rej_small, borderColor=(0, 0, 255))
        print("\nNIE ZNALEZIONO markera.")
        print("Sprawdź:")
        print("  1. Czy marker był wydrukowany na PAPIERZE (nie z ekranu)?")
        print("  2. Czy wokół markera jest biała ramka (≥1cm)?")
        print("  3. Czy marker jest DICT_6X6_250? Wygeneruj go skryptem w repozytorium.")

    disp_h = min(vis.shape[0], 800)
    disp_w = int(vis.shape[1] * disp_h / vis.shape[0])
    cv2.imshow("ArUco debug — ESC aby zamknac", cv2.resize(vis, (disp_w, disp_h)))
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
