# SmartSurveil (Shoplifting Detection)

SmartSurveil is a shoplifting detection project using your trained Keras models with:
- FastAPI backend for inference APIs
- React + Vite frontend dashboard
- Multi-model comparison test bench

## Final Project Structure

```
Shoplifting FYP/
  backend/
    __init__.py
    app.py
    inference.py
  frontend/
    index.html
    package.json
    postcss.config.mjs
    vite.config.js
    public/
    src/
  models/
    model_d1.keras
    model_d2.keras
    model_mixed.keras
  dataset/
    train/
    test/
  test_bench.py
  README.md
```

## 1) Prerequisites

- Python 3.10+
- Node.js 18+
- npm
- Windows PowerShell
- Git LFS

Install and initialize Git LFS once:

```powershell
git lfs install
```

## 2) Backend Setup (first time)

From project root:

```powershell
cd "C:/DATA E/Shoplifting FYP"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install tensorflow opencv-python fastapi uvicorn python-multipart requests
```

## 3) Frontend Setup (first time)

```powershell
cd "C:/DATA E/Shoplifting FYP/frontend"
npm install
npm install -D @tailwindcss/postcss
```

## 4) Run the Project (every time you start laptop)

Open two terminals.

### Terminal A: Start backend

```powershell
cd "C:/DATA E/Shoplifting FYP"
.\.venv\Scripts\Activate.ps1
python -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

### Terminal B: Start frontend

```powershell
cd "C:/DATA E/Shoplifting FYP/frontend"
npm run dev
```

Then open the URL shown by Vite (usually `http://localhost:5173` or `http://localhost:5174`).

## 5) Quick Health Check

```powershell
cd "C:/DATA E/Shoplifting FYP"
.\.venv\Scripts\Activate.ps1
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"
```

Expected:

```json
{"status":"ok"}
```

## 6) Test Bench

```powershell
cd "C:/DATA E/Shoplifting FYP"
.\.venv\Scripts\Activate.ps1
python test_bench.py --video "dataset/test/ShopLifting/shop_lifter_65.mp4"
```

## 7) API Endpoints Used by Frontend

- `GET /health`
- `POST /predict`
- `POST /predict/compare`
- `POST /predict/webcam`

## Notes

- Keep model files inside `models/` with the same names.
- If you clone this repository on a new machine, run `git lfs pull` in the project root to download model binaries.
- If frontend says backend offline, set API URL in the dashboard header to `http://localhost:8000`.
- First run may download EfficientNetV2B0 weights for feature extraction.
