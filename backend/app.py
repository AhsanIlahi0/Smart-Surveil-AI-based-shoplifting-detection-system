import base64
import os
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np
import tensorflow as tf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from tensorflow.keras.applications.efficientnet_v2 import EfficientNetV2B0, preprocess_input

from backend.inference import extract_shoplifting_probability, load_model

ROOT_DIR = Path(__file__).resolve().parents[1]

MODEL_CONFIG = {
    "A": {
        "path": ROOT_DIR / "models" / "model_mixed.keras",
        "threshold": 0.83,
        "dataset": "Combined D1+Lab",
    },
    "B": {
        "path": ROOT_DIR / "models" / "model_d1.keras",
        "threshold": 0.37,
        "dataset": "D1 Only",
    },
    "C": {
        "path": ROOT_DIR / "models" / "model_d2.keras",
        "threshold": 0.78,
        "dataset": "Lab Only",
    },
}


class WebcamRequest(BaseModel):
    frames_b64: List[str]
    model: str


app = FastAPI(title="SmartSurveil API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@lru_cache(maxsize=3)
def get_cached_model(model_key: str) -> tf.keras.Model:
    cfg = MODEL_CONFIG[model_key]
    model_path = cfg["path"]
    if not model_path.exists():
        raise FileNotFoundError(f"Missing model file: {model_path}")
    return load_model(str(model_path))


@lru_cache(maxsize=1)
def get_feature_extractor() -> tf.keras.Model:
    return EfficientNetV2B0(include_top=False, pooling="avg", weights="imagenet")


def _sample_video_frames(video_path: str, num_frames: int) -> List[np.ndarray]:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")

    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames: List[np.ndarray] = []

    if total > 0:
        idxs = np.linspace(0, max(total - 1, 0), num_frames, dtype=np.int32)
        for idx in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if ok and frame is not None:
                frames.append(frame)
    else:
        while len(frames) < num_frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            frames.append(frame)

    cap.release()

    if not frames:
        raise ValueError("No frames could be extracted from the video.")

    while len(frames) < num_frames:
        frames.append(frames[-1].copy())

    return frames[:num_frames]


def _decode_webcam_frames(frames_b64: List[str]) -> List[np.ndarray]:
    frames: List[np.ndarray] = []
    for img_b64 in frames_b64:
        binary = base64.b64decode(img_b64)
        arr = np.frombuffer(binary, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is not None:
            frames.append(frame)

    if not frames:
        raise ValueError("No valid webcam frames received.")

    return frames


def _prepare_raw_frame_input(frames_bgr: List[np.ndarray], time_steps: int, h: int, w: int) -> np.ndarray:
    seq = list(frames_bgr)
    while len(seq) < time_steps:
        seq.append(seq[-1].copy())
    seq = seq[:time_steps]

    processed = []
    for frame in seq:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (w, h), interpolation=cv2.INTER_AREA)
        processed.append(resized.astype(np.float32) / 255.0)

    arr = np.asarray(processed, dtype=np.float32)
    return np.expand_dims(arr, axis=0)


def _prepare_feature_sequence_input(frames_bgr: List[np.ndarray], time_steps: int, feat_dim: int) -> np.ndarray:
    seq = list(frames_bgr)
    while len(seq) < time_steps:
        seq.append(seq[-1].copy())
    seq = seq[:time_steps]

    resized_rgb = []
    for frame in seq:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (224, 224), interpolation=cv2.INTER_AREA)
        resized_rgb.append(resized.astype(np.float32))

    frame_batch = np.asarray(resized_rgb, dtype=np.float32)
    frame_batch = preprocess_input(frame_batch)

    extractor = get_feature_extractor()
    features = extractor.predict(frame_batch, verbose=0)

    extracted_dim = int(features.shape[1])
    if extracted_dim < feat_dim:
        features = np.pad(features, ((0, 0), (0, feat_dim - extracted_dim)), mode="constant")
    elif extracted_dim > feat_dim:
        features = features[:, :feat_dim]

    return np.expand_dims(features.astype(np.float32), axis=0)


def _prepare_input_for_model(model: tf.keras.Model, frames_bgr: List[np.ndarray]) -> np.ndarray:
    shape = model.input_shape
    if not isinstance(shape, tuple):
        raise ValueError(f"Unsupported model input shape container: {shape}")

    if len(shape) == 5:
        _, t, h, w, c = shape
        t = 20 if t is None else int(t)
        h = 224 if h is None else int(h)
        w = 224 if w is None else int(w)
        c = 3 if c is None else int(c)
        if c != 3:
            raise ValueError(f"Expected RGB input channels=3, got channels={c}")
        return _prepare_raw_frame_input(frames_bgr, time_steps=t, h=h, w=w)

    if len(shape) == 3:
        _, t, f = shape
        t = 16 if t is None else int(t)
        f = 1280 if f is None else int(f)
        return _prepare_feature_sequence_input(frames_bgr, time_steps=t, feat_dim=f)

    raise ValueError(f"Unsupported model input shape: {shape}")


def _encode_sampled_frames(frames_bgr: List[np.ndarray]) -> List[Dict[str, object]]:
    output: List[Dict[str, object]] = []
    for idx, frame in enumerate(frames_bgr, start=1):
        thumb = cv2.resize(frame, (224, 224), interpolation=cv2.INTER_AREA)
        ok, encoded = cv2.imencode(".jpg", thumb, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            continue
        output.append({
            "frame_index": idx,
            "image_b64": base64.b64encode(encoded.tobytes()).decode("utf-8"),
        })
    return output


def _estimate_frame_probabilities(probability: float, n_frames: int = 16) -> List[float]:
    x = np.linspace(-2.5, 2.5, n_frames, dtype=np.float32)
    curve = 1.0 / (1.0 + np.exp(-x))
    centered = curve - np.mean(curve)
    scaled = np.clip(probability + centered * 0.22, 0.0, 1.0)
    return [float(v) for v in scaled]


def _predict_for_model(model_key: str, frames_bgr: List[np.ndarray]) -> Dict[str, object]:
    model = get_cached_model(model_key)
    model_input = _prepare_input_for_model(model, frames_bgr)
    cfg = MODEL_CONFIG[model_key]

    started = time.perf_counter()
    pred = model.predict(model_input, verbose=0)
    inference_sec = round(time.perf_counter() - started, 3)

    probability = extract_shoplifting_probability(pred)
    threshold = float(cfg["threshold"])
    label = "Shoplifting" if probability >= threshold else "Normal"

    return {
        "model": model_key,
        "label": label,
        "probability": float(probability),
        "threshold": threshold,
        "dataset": cfg["dataset"],
        "inference_time_seconds": inference_sec,
        "frame_probabilities": _estimate_frame_probabilities(float(probability), n_frames=16),
        "frame_prob_estimated": True,
    }


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/predict")
async def predict(video: UploadFile = File(...), model: str = Form(...)) -> Dict[str, object]:
    model = model.strip().upper()
    if model not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid model. Use A, B, or C.")

    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await video.read())
        temp_path = tmp.name

    try:
        sampled_frames = _sample_video_frames(temp_path, num_frames=16)
        result = _predict_for_model(model, sampled_frames)
        result["sampled_frames"] = _encode_sampled_frames(sampled_frames)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/predict/compare")
async def predict_compare(video: UploadFile = File(...)) -> Dict[str, object]:
    suffix = Path(video.filename or "upload.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await video.read())
        temp_path = tmp.name

    try:
        sampled_frames = _sample_video_frames(temp_path, num_frames=16)
        results = [_predict_for_model(key, sampled_frames) for key in ["A", "B", "C"]]

        shop_count = sum(1 for r in results if r["label"] == "Shoplifting")
        majority_vote = "Shoplifting" if shop_count >= 2 else "Normal"

        return {
            "results": results,
            "majority_vote": majority_vote,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@app.post("/predict/webcam")
def predict_webcam(payload: WebcamRequest) -> Dict[str, object]:
    model = payload.model.strip().upper()
    if model not in MODEL_CONFIG:
        raise HTTPException(status_code=400, detail="Invalid model. Use A, B, or C.")

    try:
        frames = _decode_webcam_frames(payload.frames_b64)
        sampled = frames[:16]
        while len(sampled) < 16:
            sampled.append(sampled[-1].copy())

        result = _predict_for_model(model, sampled)
        result["sampled_frames"] = _encode_sampled_frames(sampled)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
