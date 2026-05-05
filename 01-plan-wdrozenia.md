# PlanKton — Plan wdrożenia (jedno zdjęcie + ROI per deska + ArUco)

> **Cel:** szczegółowy roadmap wdrożenia w architekturze klient-serwer z naciskiem na *zrozumienie dlaczego*. Każda technologia ma uzasadnienie. Pisany jako materiał edukacyjny dla osoby uczącej się DevOps.

---

## 0. Co aplikacja robi z perspektywy użytkownika

Stolarz zbudował formę (np. 1800 × 600 × 50 mm), ułożył w niej deski z żywą krawędzią, wyłożył folią i chce wiedzieć, ile żywicy epoksydowej kupić.

**Flow w aplikacji:**

1. **Wpisuje wymiary formy** — długość, szerokość, głębokość zalewu (mm).
2. **Robi jedno zdjęcie** całej formy z deskami **i markerem ArUco** w kadrze (marker leżący w płaszczyźnie desek, w widocznym miejscu poza deskami).
3. **Zaznacza ROI dla każdej deski osobno** — jeden wielokąt na deskę.
4. **Wpisuje rozmiar markera** (np. 50 mm — bok kwadratu wydrukowanego markera).
5. **Aplikacja wysyła wszystko do API**, dostaje listę pól desek.
6. **Liczy lokalnie:**
   ```
   pole_rzeki = długość_formy × szerokość_formy − Σ pole_deski
   objętość = pole_rzeki × głębokość_zalewu
   żywica_litry = objętość_mm³ / 1_000_000 × współczynnik_zapasu  (1.10 dla bezpieczeństwa)
   ```

---

## 1. Decyzje fundamentalne i ich uzasadnienie

### 1.1. Klient-serwer zamiast on-device

| Aspekt | On-device | Server-side ✓ |
|---|---|---|
| Rozmiar APK | >250 MB (Rembg + onnxruntime + opencv) | ~30 MB |
| Aktualizacja algorytmu | Build APK + Google Play review (24–48 h) | `docker compose pull` (5 min) |
| Spójność wyników | Fragmentacja po wersjach | Jeden algorytm dla wszystkich |
| Czas inferencji | 3–8 s, zależnie od telefonu | 1–3 s, kontrolowalne |
| Debug trudnych przypadków | Czarna skrzynka u klienta | Logi + fixturkę zdjęcie + reproducer |
| Wymóg internetu | Nie | Tak |
| Koszt utrzymania | 0 | ~5 €/miesiąc (VPS) |

Dla MVP w warsztacie założenie "internet jest" jest realne — planowanie zakupu żywicy odbywa się przy telefonie.

### 1.2. Stack i alternatywy

| Warstwa | Wybór | Czemu nie alternatywa |
|---|---|---|
| Klient | Kivy + Buildozer | już w projekcie |
| Backend framework | **FastAPI + Uvicorn** | najszybszy Python framework, automatyczne walidacje przez Pydantic, OpenAPI/Swagger gratis. Flask: brak walidacji. Django: overkill dla API. |
| Segmentacja | **Rembg + isnet-general-use** | zero-shot, brak treningu. SAM2: lepszy ale model 2 GB. GrabCut: gorszy na drewnie. |
| Detekcja markera | OpenCV ArUco DICT_6X6_250 | standard, sub-pikselowy refinement, szybki |
| Konteneryzacja | **Docker + docker-compose** | reprodukowalność "u mnie działa" |
| Reverse proxy | **Caddy 2** | auto-HTTPS z Let's Encrypt z 1 linii configu. Nginx + certbot: 5x więcej pracy. |
| Hosting | **Hetzner CX22** | 4.50 €/miesiąc, GDPR-friendly. AWS/GCP: drożej i bardziej skomplikowane dla MVP. |
| CI/CD | GitHub Actions | zintegrowane z repo, free tier wystarcza |
| Konfiguracja | **Pydantic Settings + .env** | walidacja typów przy starcie, czytelne błędy |
| Logowanie | **structlog (JSON)** | grep/jq-friendly. Standardowy logging: bałagan przy >100 req/dzień |
| Monitoring | UptimeRobot + Sentry | email-alert na padnięcie, łapanie wyjątków |
| Dependency mgmt | **uv** | już zdecydowane, najszybsze (Rust) |

### 1.3. Diagram architektury

```
┌─────────────────────────────────────┐                ┌─────────────────────────────┐
│  Kivy Android (klient)              │     HTTPS      │  Caddy 2 (reverse proxy)    │
│  ┌───────────────────────────────┐  │  ────────────> │  • TLS termination          │
│  │ FormDimensionsScreen          │  │                │  • Let's Encrypt auto-renew │
│  │   długość, szerokość, głęb.   │  │                │  • request_body limit 15MB  │
│  └───────────────────────────────┘  │                │  • access logs JSON         │
│  ┌───────────────────────────────┐  │                └─────────────┬───────────────┘
│  │ CaptureScreen                 │  │                              │
│  │   1 zdjęcie, marker w kadrze  │  │                              ▼
│  └───────────────────────────────┘  │                ┌─────────────────────────────┐
│  ┌───────────────────────────────┐  │                │  FastAPI (Uvicorn 2 workers)│
│  │ MultiRoiSelectorScreen        │  │                │  Endpoints:                 │
│  │   wielokąt per deska, lista   │  │                │   GET  /health              │
│  └───────────────────────────────┘  │                │   POST /v1/measure          │
│  ┌───────────────────────────────┐  │                │   GET  /v1/docs (Swagger)   │
│  │ ResultScreen                  │  │                └────────┬────────────────────┘
│  │   pola desek + objętość       │  │                         │
│  └───────────────────────────────┘  │              ┌──────────┴──────────────┐
│                                     │              ▼                         ▼
│  core/api_client.py                 │   ┌─────────────────────┐  ┌─────────────────────┐
│  core/calculator.py                 │   │ Service: aruco      │  │ Service: segment    │
└─────────────────────────────────────┘   │ • detectMarkers     │  │ • crop ROI+margin   │
                                          │ • cornerSubPix      │  │ • Rembg session     │
                                          │ • mm/px scale       │  │ • Otsu + morphology │
                                          └─────────────────────┘  │ • map back to full  │
                                                                   └─────────────────────┘
                                                            ┌─────────────────────┐
                                                            │ Service: geometry   │
                                                            │ • findContours      │
                                                            │ • largest in ROI    │
                                                            │ • area_mm² + perim  │
                                                            └─────────────────────┘
```

### 1.4. Struktura monorepo

```
PlanKton/
├── client/                       # Aplikacja Kivy (rozwinięcie obecnego kodu)
│   ├── core/
│   │   ├── api_client.py         # Komunikacja z backendem (async)
│   │   ├── calculator.py         # pole_rzeki = pole_formy − Σ pole_desek
│   │   └── state.py              # FormDimensions, BoardMeasurement
│   ├── ui/
│   │   ├── screens/
│   │   │   ├── form_dimensions.py
│   │   │   ├── capture.py
│   │   │   ├── multi_roi_selector.py
│   │   │   └── result.py
│   │   └── plankton.kv
│   ├── tests/
│   ├── main.py
│   ├── buildozer.spec
│   └── pyproject.toml
│
├── server/                       # Backend FastAPI (NOWY KOMPONENT)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py               # FastAPI entrypoint, lifespan, middleware
│   │   ├── api/
│   │   │   ├── routes.py         # POST /v1/measure
│   │   │   └── schemas.py        # Pydantic request/response
│   │   ├── services/
│   │   │   ├── aruco.py          # mm/px z markera
│   │   │   ├── segmentation.py   # Rembg z preselekcją ROI
│   │   │   ├── geometry.py       # findContours, area, perimeter
│   │   │   └── pipeline.py       # Orkiestracja end-to-end
│   │   ├── core/
│   │   │   ├── config.py         # Pydantic Settings
│   │   │   ├── logging.py        # structlog setup
│   │   │   └── exceptions.py     # Domain exceptions
│   │   └── models/
│   │       └── domain.py         # MeasurementResult dataclass
│   ├── tests/
│   │   ├── fixtures/             # 10–15 zdjęć desek + ground truth
│   │   ├── conftest.py
│   │   ├── test_aruco.py
│   │   ├── test_segmentation.py
│   │   ├── test_geometry.py
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   ├── Dockerfile
│   ├── .dockerignore
│   ├── pyproject.toml
│   └── README.md
│
├── deploy/                       # Konfiguracja deploymentu
│   ├── docker-compose.yml
│   ├── Caddyfile
│   ├── .env.example
│   └── README.md
│
├── .github/
│   └── workflows/
│       ├── server-tests.yml
│       ├── server-deploy.yml
│       ├── client-tests.yml
│       └── client-build.yml
│
├── docs/
│   ├── api-contract.md
│   ├── deployment.md
│   └── architecture-decisions.md
│
├── CLAUDE.md
├── README.md
└── .gitignore
```

**Dlaczego oddzielne `pyproject.toml` w client/ i server/:** zupełnie inne zależności. Kivy nie potrzebuje FastAPI, FastAPI nie potrzebuje Buildozera. Oddzielne lockfile = mniejsze ryzyko konfliktów wersji.

---

## 2. Faza A — Backend MVP (25–40 h)

### A.1. Inicjalizacja projektu

```bash
cd C:\repos\PlanKton
mkdir server
cd server
uv init --package plankton-server
uv add fastapi "uvicorn[standard]" python-multipart pillow numpy
uv add opencv-contrib-python rembg onnxruntime
uv add structlog pydantic-settings
uv add --dev pytest pytest-asyncio httpx ruff mypy
```

**Co robi każda zależność:**

| Pakiet | Po co |
|---|---|
| `fastapi` | Framework HTTP. Funkcja Pythona + dekorator → walidacja, OpenAPI, parsing — gratis. |
| `uvicorn[standard]` | Serwer ASGI uruchamiający FastAPI. `[standard]` = uvloop + httptools (szybciej na Linuxie) |
| `python-multipart` | Wymóg do `UploadFile` (multipart/form-data dla upload zdjęć) |
| `pillow` | Rembg używa PIL wewnętrznie do I/O |
| `opencv-contrib-python` | OpenCV z modułami contrib (ArUco). `opencv-python` (bez contrib) nie ma ArUco w nowszych wersjach. |
| `rembg` | Pakiet segmentacji; modele ONNX pobiera przy pierwszym `new_session()` |
| `onnxruntime` | Silnik inferencji modeli Rembg na CPU. Dla GPU: `onnxruntime-gpu`. |
| `structlog` | Logowanie strukturalne JSON — kluczowe dla observability |
| `pydantic-settings` | Konfiguracja ze zmiennych środowiskowych z walidacją typów |
| `pytest-asyncio` | Testy async (FastAPI używa async) |
| `httpx` | Klient HTTP do testów API (TestClient FastAPI używa httpx) |
| `ruff` | Linter + formatter. 100x szybszy niż flake8 + black + isort. |
| `mypy` | Type checker. Łapie błędy zanim trafią na produkcję. |

### A.2. Pierwszy działający endpoint

`server/app/main.py`:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.core.config import settings
from app.core.logging import setup_logging
from app.services.segmentation import warmup_rembg

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    warmup_rembg()  # ładuje model przy starcie, nie przy pierwszym requeście
    yield

app = FastAPI(title="PlanKton API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/v1")

@app.get("/health")
def health():
    return {"status": "ok", "version": app.version}
```

**Co tu się dzieje:**

- **`lifespan`** — kontekst manager wywoływany raz przy starcie serwera i raz przy zamknięciu. To miejsce na "warmup" — pobranie modelu, połączenie z DB, prefetch. Bez tego pierwszy request musiałby czekać na ładowanie modelu (kilka sekund złego UX).
- **`include_router(router, prefix="/v1")`** — wszystkie endpointy z `routes.py` są prefiksowane `/v1`. Wersjonowanie API od pierwszego dnia — przyszły refactor (`/v2`) nie zepsuje klientów na `/v1`.
- **CORS middleware** — Cross-Origin Resource Sharing. Bez tego przeglądarka blokuje requesty z innych domen. Klient mobilny tego nie potrzebuje, ale dokumentacja Swaggera w przeglądarce tak.
- **`/health`** — endpoint dla load balancera, monitoringu, healthcheck Dockera.

**Uruchomienie lokalnie:**
```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

`--reload` — serwer obserwuje pliki, restartuje się przy zapisie. **Tylko do dev**, produkcyjnie wyłączyć.

Otwórz `http://localhost:8000/v1/docs` — masz interaktywny Swagger gratis. Główny tool debugu.

### A.3. Kontrakt API — Pydantic schemas

`server/app/api/schemas.py`:

```python
from pydantic import BaseModel, Field, field_validator

class RoiPolygon(BaseModel):
    """Wielokąt definiujący jedną deskę w pikselach pełnego obrazu."""
    points: list[list[float]] = Field(..., min_length=3)
    label: str | None = None  # np. "deska 1", do wyświetlenia w wynikach

    @field_validator("points")
    @classmethod
    def each_point_has_two_coords(cls, v):
        for p in v:
            if len(p) != 2:
                raise ValueError("każdy punkt musi być [x, y]")
        return v

class BoardMeasurement(BaseModel):
    label: str | None
    area_mm2: float
    perimeter_mm: float
    contour: list[list[float]]  # do narysowania w aplikacji

class MeasureResponse(BaseModel):
    mm_per_px: float
    boards: list[BoardMeasurement]
    total_area_mm2: float
    debug: dict | None = None  # opcjonalnie w trybie dev
```

Request leci jako multipart (zdjęcie + JSON metadanych). FastAPI obsługuje to elegancko przez `Form` i `File`.

**Dlaczego Pydantic:** to nie tylko dokumentacja. Każdy request jest walidowany automatycznie. Klient wyśle `marker_size_mm: -5` → 422 Unprocessable Entity z czytelnym komunikatem. Zero kodu walidacji do napisania.

### A.4. Endpoint — POST /v1/measure

`server/app/api/routes.py`:

```python
import json
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import numpy as np
import cv2
from app.api.schemas import MeasureResponse
from app.services.pipeline import measure_boards
from app.core.config import settings
from app.core.logging import log

router = APIRouter()

@router.post("/measure", response_model=MeasureResponse)
async def measure(
    image: UploadFile = File(...),
    rois_json: str = Form(...),
    marker_size_mm: float = Form(..., gt=0, le=1000),
):
    # 1. Walidacja rozmiaru pliku
    raw = await image.read()
    if len(raw) > settings.max_image_size_mb * 1024 * 1024:
        raise HTTPException(413, f"Plik > {settings.max_image_size_mb} MB")

    # 2. Dekodowanie obrazu
    arr = np.frombuffer(raw, np.uint8)
    img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(400, "Nie udało się zdekodować obrazu")

    # 3. Parsowanie ROI
    try:
        rois = json.loads(rois_json)
    except json.JSONDecodeError:
        raise HTTPException(400, "Nieprawidłowy JSON ROI")

    # 4. Wywołanie pipeline'u
    log.info("measure_started",
             image_shape=img_bgr.shape,
             num_rois=len(rois),
             marker_size_mm=marker_size_mm)
    result = measure_boards(img_bgr, rois, marker_size_mm)
    log.info("measure_completed",
             total_area_mm2=result.total_area_mm2,
             mm_per_px=result.mm_per_px)
    return result
```

**Punkty edukacyjne:**

- **`async def`** — FastAPI lubi async handlery. `await image.read()` zwalnia event loop podczas wczytywania pliku. Jeśli wewnątrz wołasz CPU-bound (cv2, Rembg), to **i tak blokuje thread** — można rozważyć `run_in_executor`, ale dla MVP to overkill.
- **`HTTPException`** — czytelne błędy HTTP. FastAPI zwraca JSON `{"detail": "..."}` z odpowiednim status code.
- **`response_model=MeasureResponse`** — gwarantuje, że nawet jeśli pipeline zwróci coś dziwnego, FastAPI odfiltruje pola spoza schematu. Bezpieczeństwo + dokumentacja.

### A.5. Service layer — separacja domen

**Filozofia:** endpoint w `routes.py` parsuje request, woła service, zwraca response. Cała logika biznesowa w `services/`.

**Dlaczego:** testowalność. Możesz przetestować `services/segmentation.py` bez stawiania serwera HTTP. Możesz wymienić framework (FastAPI → Litestar) bez przepisywania algorytmów.

`server/app/services/aruco.py`:

```python
import cv2
import numpy as np
from app.core.exceptions import ArucoNotFoundError

_DICT = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_6X6_250)

def calibrate(image_bgr: np.ndarray, marker_size_mm: float) -> float:
    """Zwraca skalę mm/px na podstawie obwodu markera."""
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    detector = cv2.aruco.ArucoDetector(_DICT, cv2.aruco.DetectorParameters())
    corners, ids, _ = detector.detectMarkers(gray)

    if ids is None or len(corners) == 0:
        raise ArucoNotFoundError("Marker ArUco nie został wykryty")

    # Sub-pikselowe doprecyzowanie rogów
    cv2.cornerSubPix(
        gray, corners[0], (5, 5), (-1, -1),