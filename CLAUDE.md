# CLAUDE.md — instrukcje dla Claude Code

> Ten plik jest czytany przez Claude Code przy każdej sesji. Opisuje projekt, architekturę, konwencje i typowe zadania, żeby Claude rozumiał kontekst bez pytania.

---

## 1. O projekcie

**PlanKton** to aplikacja mobilna na Androida (Python + Kivy + Buildozer) do obliczania objętości żywicy epoksydowej potrzebnej do zalania formy z deskami o nieregularnych krawędziach (live edge).

### Architektura: klient-serwer

- **Klient** (`client/`): Kivy + Buildozer — zdjęcie, wybór ROI, prezentacja wyniku
- **Serwer** (`server/`): FastAPI + Rembg + OpenCV — segmentacja, kalibracja ArUco, pomiar pola
- **Deploy** (`deploy/`): docker-compose + Caddy reverse proxy

### Flow użytkownika

```
1. Wpisuje wymiary formy                       → pole_formy        [mm²]
2. Robi JEDNO zdjęcie układu z markerem ArUco
3. Zaznacza wielokąt ROI wokół KAŻDEJ deski (multi-ROI)
4. Backend dla każdego ROI:
   - kalibracja px→mm z markera ArUco DICT_6X6_250
   - segmentacja Rembg (model isnet-general-use) na wycinku ROI z marginesem
   - obrys + pole_deski_n
5. pole_rzeki = pole_formy − Σ pole_deski_n
6. objętość = pole_rzeki × głębokość × 1.10 (10% zapasu)
```

### Strategia algorytmiczna — kluczowe decyzje

- **Jedno zdjęcie + multi-ROI**, nie dwa zdjęcia desek osobno (UX wygrał nad odrobiną dokładności).
- **Wymiary formy ręcznie**, nie z fotografii (taśma miernicza dokładniejsza niż homografia).
- **Rembg per ROI z marginesem 10%**, nie cały obraz (mniej szumu, marker poza ROI nie konkuruje).
- **Folia w zdjęciu zostawiamy** dopóki nie udowodnimy że psuje pomiar (empiryczna inżynieria).

---

## 2. Struktura repozytorium

```
PlanKton/
├── client/                  # Aplikacja Kivy
│   ├── core/               # api_client, calculator, state
│   ├── ui/                 # screens, plankton.kv
│   ├── tests/
│   ├── main.py
│   ├── buildozer.spec
│   └── pyproject.toml
├── server/                  # Backend FastAPI
│   ├── app/
│   │   ├── main.py         # FastAPI entrypoint + lifespan
│   │   ├── api/            # routes.py, schemas.py
│   │   ├── services/       # aruco, segmentation, geometry, pipeline
│   │   ├── core/           # config, logging, exceptions
│   │   └── models/         # domain dataclasses
│   ├── tests/fixtures/     # zdjęcia testowe + ground truth
│   ├── Dockerfile
│   └── pyproject.toml
├── deploy/
│   ├── docker-compose.yml
│   ├── Caddyfile
│   └── .env.example
├── .github/workflows/
│   ├── server-tests.yml
│   ├── server-deploy.yml
│   ├── client-tests.yml
│   └── client-build.yml
├── docs/
│   ├── api-contract.md
│   ├── deployment.md
│   └── architecture-decisions.md
├── CLAUDE.md               # ten plik
└── README.md
```

**Ważne:** `client/` i `server/` mają OSOBNE `pyproject.toml` i lockfile — nie mieszaj zależności między nimi.

---

## 3. Stack technologiczny

### Backend (`server/`)

| Komponent | Technologia | Po co |
|---|---|---|
| Framework HTTP | FastAPI + Uvicorn | Async, Pydantic, OpenAPI za darmo |
| Segmentacja | Rembg + `isnet-general-use` | Zero-shot, brak trenowania |
| CV utilities | opencv-contrib-python | ArUco DICT_6X6_250, findContours |
| Walidacja | Pydantic Settings | Konfiguracja z env vars |
| Logowanie | structlog (JSON) | grep/jq-friendly |
| Smoothing | scipy.signal.savgol_filter | Wygładzanie konturu |
| Zarządzanie zależnościami | **uv** | Już zdecydowane, używaj zawsze |

### Klient (`client/`)

| Komponent | Technologia |
|---|---|
| Framework UI | Kivy |
| Build APK | Buildozer |
| Komunikacja HTTP | `kivy.network.urlrequest.UrlRequest` (NIE `requests` synchroniczne) |

### DevOps

| Komponent | Technologia |
|---|---|
| Konteneryzacja | Docker (multi-stage builds) |
| Reverse proxy | Caddy 2 (auto-HTTPS Let's Encrypt) |
| Hosting | Hetzner CX22 |
| CI/CD | GitHub Actions |
| Container registry | GitHub Container Registry (`ghcr.io`) |
| Monitoring | UptimeRobot + Sentry (opcjonalnie) |

---

## 4. Konwencje kodu

### 4.1. Pythonowe

- **Python 3.12** w server, **3.11** w client (Buildozer kompatybilność).
- **Type hints zawsze** — `mypy` w CI.
- **Ruff** jako linter+formatter, nie black+isort+flake8.
- **f-stringi**, nie `.format()` ani `%`.
- **Dataclasses** dla domain models, **Pydantic** dla API contractów.
- **Async tylko gdy ma sens** — endpointy FastAPI tak (mogą być wywoływane konkurencyjnie), ale services synchroniczne (Rembg/OpenCV są CPU-bound, async nic nie daje).

### 4.2. Architektura warstwowa (server)

```
routes.py    →  parsuje request, mapuje wyjątki na HTTP, zwraca Pydantic response
   ↓
services/    →  cała logika domeny (algorytmy CV, kalibracja, geometria)
   ↓
core/        →  cross-cutting: config, logging, exceptions
```

**Zasada żelazna:** services NIE wiedzą o HTTP. Wyrzucają domain exceptions (`ArucoNotFoundError`, `ContourNotFoundError`), które routes mapują na statusy HTTP.

### 4.3. Konwencje nazewnicze

- Pliki: `snake_case.py`
- Klasy: `PascalCase`
- Funkcje, zmienne: `snake_case`
- Stałe modułowe: `UPPER_SNAKE_CASE`
- Pola Pydantic: `snake_case` (FastAPI domyślnie tłumaczy na snake_case w JSON)

### 4.4. Nazwy commitów (Conventional Commits)

```
feat: add multi-ROI selector widget
fix: correct kivy-to-image coordinate mapping
refactor: extract aruco calibration to service
test: add fixture for two-board layout
docs: update API contract for multi-roi
chore: bump opencv-contrib-python to 4.10
ci: cache uv dependencies in github actions
```

---

## 5. Konwencje testów

### 5.1. Struktura

- **Unit:** funkcja izolowana, mockuje zależności (np. `aruco.calibrate` bez zdjęcia)
- **Integration:** kilka warstw razem, bez HTTP (np. cały `pipeline.measure_boards`)
- **API/E2E:** TestClient FastAPI, request → response

### 5.2. Fixtures

`server/tests/fixtures/` zawiera:
- Zdjęcia desek z markerem ArUco
- `ground_truth.json` z polami zmierzonymi fizycznie suwmiarką
- Tolerancja w testach: 10% (akceptowalne dla zakupu żywicy)

**Każda zmiana algorytmu odpala pełny pytest** — to jest regression test set.

### 5.3. Co testować

✅ Zawsze:
- Każda funkcja w `services/` (unit)
- Pełen pipeline z fixture (integration)
- Endpointy z TestClient (API)
- Walidacja Pydantic w schemas

❌ Nie testuj:
- Wnętrzności Rembg, OpenCV, FastAPI (zaufaj bibliotekom)
- Magic numbers w morfologii (test wyniku, nie implementacji)

---

## 6. Typowe zadania — jak je formułować

### 6.1. "Dodaj nowy endpoint"

```
1. Schema w server/app/api/schemas.py (Pydantic Request + Response)
2. Logika w server/app/services/{nowy_serwis}.py
3. Endpoint w server/app/api/routes.py wywołujący service
4. Test w server/tests/test_api.py (TestClient)
5. Aktualizacja docs/api-contract.md
```

### 6.2. "Zmień algorytm segmentacji"

```
1. Edytuj tylko server/app/services/segmentation.py
2. Zachowaj tę samą sygnaturę funkcji segment_in_roi(image_bgr, roi_polygon)
3. Odpal pełny pytest — fixtures sprawdzą czy nie pogorszyło
4. Jeśli pogorszyło ground truth, popraw model lub wycofaj zmianę
5. Udokumentuj decyzję w docs/architecture-decisions.md (nowy ADR)
```

### 6.3. "Dodaj walidację"

```
- Walidacja inputu HTTP → Pydantic w schemas.py (Field(gt=0, max_length=20, ...))
- Walidacja domeny → custom exception w core/exceptions.py + raise w service
- NIGDY walidacja w routes.py (brzydki kod)
```

### 6.4. "Dodaj logowanie"

```python
from app.core.logging import log

# Zawsze JSON-friendly: kluczowe dane jako kwargs, nie f-string
log.info("event_name", key1=value1, key2=value2)        # ✅
log.info(f"Something happened with {x}")                # ❌ niewytypowane
```

### 6.5. "Dodaj zależność"

```bash
# Server
cd server && uv add NAZWA_PAKIETU
# albo dev-only:
cd server && uv add --dev NAZWA_PAKIETU

# Client
cd client && uv add NAZWA_PAKIETU
```

**Po dodaniu sprawdź `uv.lock` w gicie** — to jest kluczowe dla reprodukowalności.

---

## 7. Pułapki i częste bugi

### 7.1. Współrzędne ekran ↔ piksele

**Problem #1 w aplikacjach Kivy ze zdjęciami.** Kivy renderuje obraz w jakichś wymiarach na ekranie (np. 1080×1920), ale plik na dysku to np. 4000×3000 px. **ROI MUSI być zapisany w pikselach oryginalnego pliku**, bo tam działa serwer.

W `client/ui/screens/multi_roi.py` zawsze testuj `_kivy_to_image_coords()` z konkretnym fixture'em.

### 7.2. OpenCV brakuje libgl1

`python:slim` w Dockerze nie ma libgl1. Bez `apt install libgl1` `import cv2` rzuca `ImportError: libGL.so.1`. Pamiętaj w Dockerfile.

### 7.3. Rembg pobiera model przy każdym requeście

Bez `warmup_session()` w lifespan, każdy `new_session()` pobiera model z internetu (170 MB). Pre-download w Dockerfile + warmup w lifespan = obowiązkowe.

### 7.4. ArUco w `opencv-python` (bez contrib) nie istnieje

Od OpenCV 4.7 ArUco jest tylko w `opencv-contrib-python`. Pip pakiet `opencv-python` nie działa.

### 7.5. Kivy `requests.post` zamraża UI

Synchroniczny HTTP w głównym wątku Kivy = ANR (Application Not Responding) na Androidzie. Używaj `kivy.network.urlrequest.UrlRequest` lub `threading.Thread` + `Clock.schedule_once` dla callbacka.

### 7.6. Docker compose `:latest` tag

`image: plankton-api:latest` w compose działa, ale rollback jest niemożliwy. W produkcji dojrzałej pinujesz SHA. Dla MVP `:latest` jest OK ale wiedz że to compromise.

### 7.7. UFW i Docker

Docker domyślnie pomija UFW i otwiera porty bezpośrednio przez iptables. Dlatego w `docker-compose.yml` używamy `expose:` (wewnętrznie) zamiast `ports:` (na świat) dla API. Tylko Caddy ma `ports: - "443:443"`.

---

## 8. Komendy które będziesz najczęściej uruchamiał

### Backend dev

```bash
cd server

# Setup
uv sync

# Dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Testy
uv run pytest
uv run pytest tests/test_pipeline.py -v
uv run pytest --cov=app

# Lint + format
uv run ruff check .
uv run ruff format .
uv run mypy app
```

### Klient dev (na desktopie)

```bash
cd client
uv sync
uv run python main.py
```

### Build APK (lokalnie, tylko Linux/WSL)

```bash
cd client
buildozer android debug
```

### Docker lokalnie

```bash
cd deploy
docker compose up --build
docker compose logs -f api
docker compose down
```

### Deploy na VPS (po push do main)

CI robi to automatycznie. Manualnie:
```bash
ssh plankton@VPS_IP
cd /opt/plankton/deploy
docker compose pull
docker compose up -d --remove-orphans
docker image prune -f
```

---

## 9. Plik `.env` — co tam jest

**`.env` LOKALNY** (w `.gitignore`):
```
LOG_LEVEL=DEBUG
DEBUG=true
```

**`.env.example`** (commitujesz):
```
LOG_LEVEL=INFO
REMBG_MODEL=isnet-general-use
MAX_IMAGE_SIZE_MB=15
CORS_ORIGINS=["https://api.plankton.example.com"]
SENTRY_DSN=
```

Na VPS w `/opt/plankton/deploy/.env` masz produkcyjne wartości.

---

## 10. Sekrety GitHub (Settings → Secrets → Actions)

- `VPS_HOST` — IP serwera Hetzner
- `VPS_USER` — `plankton`
- `VPS_SSH_KEY` — prywatny klucz ed25519 (cały content z BEGIN/END)
- `SENTRY_DSN` — opcjonalnie

---

## 11. Nauka Git & DevOps — plan i zadania osobiste

> Projekt jest celowo zaprojektowany jako praktyczna szkoła git + devops. Zadania oznaczone 🎓 musisz wykonać **osobiście** — Claude wyjaśnia i podpowiada, ale nie klika za Ciebie. Tylko tak się nauczysz.

### 11.0. 🎓 REGUŁA: Wyjaśniaj CEL każdej komendy Git

**ZASADA:** Zanim wpisujesz komendę, zawsze wyjaśniam:
1. **CO robi** — co komenda wykonuje (funkcja)
2. **PO CO teraz** — czemu jest potrzebna w tym momencie (kontekst)
3. **Oczekiwany output** — co powinieneś zobaczyć jeśli się powiodła

**Format wyjaśnienia:**
```bash
# Komenda
git status

# CO robi: Sprawdza obecny stan working tree (zmienione, staged, untracked pliki)
# PO CO TERAZ: Pre-flight check — chcemy pracować na czystym stanie przed zmianami
# OUTPUT: "On branch X", "nothing to commit, working tree clean" lub lista zmian
```

**Dlaczego to ważne?**
- Bez zrozumienia **po co** komendy wykonujemy, będziesz je kopipastować bez sensu
- Zrozumienie celu = umiejętność debugowania gdy coś pójdzie nie tak
- Git ma ~150 komend, ale logika jest zawsze taka sama — jeśli rozumiesz **czemu**, reszta jest łatwa

**Jeśli kiedykolwiek powiem komendę BEZ wyjaśnienia — **popraw mnie** i powiedz "czemu?"**

### 11.1. Mapa nauki — co opanować i kiedy

| Faza projektu | Git / DevOps — co się nauczysz |
|---|---|
| A — Backend MVP | `commit`, `branch`, `merge`, Pull Request, `.gitignore` |
| B — Docker | `tag`, `git log`, Docker image workflow, `.dockerignore` |
| C — CI/CD | GitHub Actions triggers, `push --tags`, branch protection, secrets |
| D — VPS deploy | SSH keys, `git revert`, rollback, `reflog` |
| E+ — dalej | `rebase -i`, `bisect`, `worktree`, multi-stage Docker |

---

### 11.2. Faza A — Git basics (zrób to ręcznie)

**Koncepty:** staging area, commit jako snapshot, branch jako wskaźnik, remote vs local.

#### Pre-flight check (KAŻDY RAZ ZANIM ZACZNIESZ PRACOWAĆ)

```bash
# 🎯 CEL: Sprawdzić czy working tree jest czysty i orientować się w branczach

git status
# CO robi: Pokazuje zmienione, staged, untracked pliki w aktualnym branchu
# PO CO TERAZ: Chcemy pracować ze czystego stanu (nic niespushowanego)
# OCZEKIWANY OUTPUT: "nothing to commit, working tree clean"

git branch -a
# CO robi: Listuje WSZYSTKIE branche (lokalne + zdalne na GitHub)
# PO CO TERAZ: Orientacja — czy istnieje main? Czy są stare branche?
# OCZEKIWANY OUTPUT: "* main", "remotes/origin/main"

git log --oneline -n 5
# CO robi: Pokazuje ostatnie 5 commitów w skróconym formacie (hash + message)
# PO CO TERAZ: Historia — co już jest zacommittowane?
# OCZEKIWANY OUTPUT: Lista ostatnich commitów (README.md, CLAUDE.md, etc)
```

🎓 **Zadania osobiste:**
- [ ] Stwórz pierwszy commit projektu ręcznie: `git add`, `git commit -m "feat: ..."`
- [ ] Utwórz feature branch: `git checkout -b feat/server-init`
- [ ] Wypchnij branch: `git push -u origin feat/server-init`
- [ ] Otwórz Pull Request na GitHub (przez UI) i go zmerguj
- [ ] Usuń lokalnie zmergowany branch: `git branch -d feat/server-init`

**Komendy do poznania (zawsze z wyjaśnieniami):**
```bash
git diff
# CO robi: Pokazuje dokładne różnice w plikach (linie dodane/usunięte)
# PO CO: Przegląd zmian przed commitem

git log --oneline --graph
# CO robi: Historia commitów jako graf (wizualizacja branchy)
# PO CO: Zrozumieć strukturę branchy i merge pointy

git stash / git stash pop
# CO robi: Zapamiętaj zmiany na "półce" bez commitu
# PO CO: Schować zmian na chwilę bez commitowania
```

---

### 11.3. Faza B — Tagowanie i Docker workflow

**Koncepty:** tagi jako niezmienne punkty historii, `.gitignore` vs `.dockerignore`, obrazy Docker jako artefakty.

🎓 **Zadania osobiste:**
- [ ] Utwórz `.gitignore` i wyjaśnij sobie dlaczego `__pycache__/`, `.env`, `*.pyc` tam są
- [ ] Oznacz pierwszy działający build: `git tag v0.1.0 && git push origin v0.1.0`
- [ ] Sprawdź różnicę między `git tag` (lokalny) a `git push origin v0.1.0` (zdalny)
- [ ] Zrób `docker build` lokalnie i sprawdź `docker images` — rozumiesz warstwy?

**Komendy do poznania:**
```bash
git tag -a v0.1.0 -m "First working server"
git tag                         # lista tagów
git show v0.1.0                 # co zawiera ten tag?
git log --oneline v0.1.0..HEAD  # co się zmieniło od tagu?
```

---

### 11.4. Faza C — GitHub Actions i branch protection

**Koncepty:** CI jako automatyczny `pytest` po każdym pushu, secrets jako env vars w Actions, branch protection = wymuszenie PR.

🎓 **Zadania osobiste:**
- [ ] Napisz pierwszy workflow `server-tests.yml` SAM (Claude może pomóc strukturą, ale wpisz to ręcznie)
- [ ] Włącz branch protection na `main` w GitHub: Settings → Branches → Add rule → "Require status checks"
- [ ] Dodaj sekrety VPS w GitHub: Settings → Secrets → Actions (nie wklejaj ich nigdzie indziej)
- [ ] Celowo zepsuj test i obserwuj jak CI failuje — to jest punkt zwrotny w rozumieniu CI

**Kluczowe do zrozumienia w workflow YAML:**
```yaml
on:
  push:
    branches: [main]        # trigger: push na main
  pull_request:
    branches: [main]        # trigger: PR do main

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4   # git clone w CI
      - run: uv run pytest          # twój command
```

---

### 11.5. Faza D — SSH, deploy i rollback

**Koncepty:** klucz SSH jako poświadczenie bez hasła, `git revert` jako bezpieczne cofnięcie, `reflog` jako siatka bezpieczeństwa.

🎓 **Zadania osobiste:**
- [ ] Wygeneruj parę kluczy SSH dla GitHub Actions: `ssh-keygen -t ed25519 -C "plankton-ci"`
- [ ] Dodaj klucz publiczny do VPS (`~/.ssh/authorized_keys`) — ręcznie przez SSH
- [ ] Przetestuj połączenie z lokalnego: `ssh -i ~/.ssh/plankton-ci plankton@VPS_IP`
- [ ] Zasymuluj błędny deploy: zrób commit z błędem → push → obserwuj CI → zrób `git revert HEAD` → push

**Komendy ratunkowe (naucz się zanim będą potrzebne):**
```bash
git reflog                      # lista WSZYSTKICH ruchów HEAD — Twoja siatka bezpieczeństwa
git revert HEAD                 # cofnij ostatni commit (bezpieczne — tworzy nowy commit)
git reset --hard HEAD~1         # cofnij commit (NIEBEZPIECZNE jeśli już pushowałeś)
git cherry-pick <hash>          # przenieś pojedynczy commit z innego brancha
```

---

### 11.6. Zaawansowane — kiedy projekt działa

Wróć do tych tematów gdy MVP jest na produkcji:

| Temat | Kiedy | Po co |
|---|---|---|
| `git rebase -i` | Przed merge dużego brancha | Wyczyść historię commitów (squash) |
| `git bisect` | Gdy test failuje ale nie wiesz od kiedy | Binarnie znajdź który commit zepsuł |
| `git worktree` | Gdy chcesz testować dwa branche jednocześnie | Dwa foldery, jeden repo |
| Multi-stage Docker | Przy optymalizacji obrazu produkcyjnego | Builder oddzielnie od runtime |
| `docker buildx` + GHCR | Przy automatycznym build w CI | Buduj raz, deployuj wszędzie |

---

### 11.7. Instrukcja dla Claude — przy zadaniach git

> Gdy Claude widzi zadanie oznaczone 🎓, **NIE wykonuje go samodzielnie**. Wyjaśnia koncepcję, podaje dokładną komendę, i czeka aż użytkownik ją wpisze. Wyjątek: użytkownik explicite prosi "zrób to za mnie".

---

## 12. Jak pracować w sesji Claude Code

### 11.1. Dobre prompty

```
✅ "W server/app/services/aruco.py dodaj funkcję która zwraca też homografię
   z 4 rogów markera, żeby później zrobić korekcję perspektywy"

✅ "Napisz test test_segmentation.py używający fixture dwie_deski.jpg,
   sprawdź że zwraca dokładnie 2 maski o niezerowym polu"

✅ "Dodaj walidację w schemas.py że roi.polygon ma <= 100 punktów
   (bezpieczeństwo przed atakiem przez wielki JSON)"
```

### 11.2. Złe prompty

```
❌ "Zrób całą aplikację" — za szerokie, pracuj inkrementalnie
❌ "Popraw kod" — co konkretnie? Co masz na myśli?
❌ "Dodaj funkcję która segmentuje" — w jakim pliku? Z jaką sygnaturą?
```

### 11.3. Workflow

1. **Jedno zadanie = jeden plik lub jedna funkcja**
2. **Po każdej zmianie odpal `pytest`** w `server/`
3. **Commituj często** (małe atomowe commity, conventional commits)
4. **Aktualizuj `docs/architecture-decisions.md`** dla nieoczywistych decyzji
5. **Aktualizuj testy fixtures** gdy zmieniasz algorytm — ground truth nadal musi się zgadzać

---

## 12. Status implementacji

> Aktualizuj tę sekcję podczas pracy.

### Faza A — Backend MVP + Git basics
- [ ] A.0. 🎓 Pierwszy branch + PR (feat/server-init)
- [ ] A.1. Inicjalizacja `server/` z `uv`
- [ ] A.2. FastAPI entrypoint + lifespan + `/health`
- [ ] A.3. Pydantic schemas (RoiInput, BoardResult, MeasureBoardsResponse)
- [ ] A.4. Service: `aruco.calibrate`
- [ ] A.4. Service: `segmentation.segment_in_roi`
- [ ] A.4. Service: `geometry.select_contour_in_roi` + `smooth_contour`
- [ ] A.4. Service: `pipeline.measure_boards`
- [ ] A.5. Endpoint `/v1/measure-boards`
- [ ] A.6. Pydantic Settings + `.env`
- [ ] A.7. structlog setup
- [ ] A.8. Custom exceptions
- [ ] A.9. Test fixtures (10–15 zdjęć + ground_truth.json)
- [ ] A.9. Testy unit/integration/API

### Faza B — Docker + Git tags
- [ ] B.0. 🎓 `git tag v0.1.0` po pierwszym działającym buildzie
- [ ] B.2. Dockerfile (multi-stage, non-root, pre-download model)
- [ ] B.3. .dockerignore
- [ ] B.4. docker-compose.yml
- [ ] B.5. Caddyfile
- [ ] B.6. Lokalny test

### Faza C — CI/CD + Branch protection
- [ ] C.0. 🎓 Branch protection na main (GitHub UI)
- [ ] C.0. 🎓 Sekrety VPS w GitHub Secrets
- [ ] C.1. server-tests.yml
- [ ] C.2. server-deploy.yml (build + push GHCR + SSH deploy)
- [ ] C.3. client-build.yml (na release tag)
- [ ] C.4. Branch protection na main

### Faza D — Hosting + SSH + Rollback
- [ ] D.0. 🎓 Generowanie klucza SSH dla Actions: `ssh-keygen -t ed25519 -C "plankton-ci"`
- [ ] D.0. 🎓 Dodanie klucza do VPS ręcznie + test połączenia
- [ ] D.0. 🎓 Symulacja rollbacku: celowy błąd → `git revert HEAD` → push
- [ ] D.2. VPS Hetzner CX22 + initial setup (non-root, UFW, fail2ban)
- [ ] D.2. Klucz SSH dla GitHub Actions w VPS_SSH_KEY
- [ ] D.3. Domena + DNS A record
- [ ] D.4. First deploy ręcznie + Let's Encrypt cert

### Faza E — Klient Kivy
- [ ] E.1. ApiClient z UrlRequest
- [ ] E.2. MultiRoiSelector (KRYTYCZNE: poprawne kivy_to_image_coords)
- [ ] E.3. AppState
- [ ] E.4. Konfiguracja PLANKTON_API_URL
- [ ] E.x. FormDimensionsScreen, CameraScreen, ResultScreen

### Faza F — Observability
- [ ] F.1. UptimeRobot monitor /health
- [ ] F.2. Sprawdzić czy logi structlog są parseowalne jq
- [ ] F.3. Sentry SDK + DSN

### Google Play release
- [ ] Konto Google Play Developer ($25 jednorazowo)
- [ ] Podpisany APK release
- [ ] Materiały marketingowe + polityka prywatności
- [ ] Internal Testing → Production
