"""
inference.py — Local model loading and inference for shoplifting detection.
Adapted from Kaggle kernel code.
"""

import os
import base64
import json
import cv2
import numpy as np
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path
import tensorflow as tf
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.applications.mobilenet_v2 import preprocess_input
from tensorflow.keras.models import load_model
from ultralytics import YOLO
from sklearn.decomposition import PCA

# Constants
WINDOW_SIZE = 16
YOLO_CONF = 0.3
CROP_PADDING = 0.10
THRESHOLDS = {"A": 0.83, "B": 0.37, "C": 0.78}
MOBILENET_DIM = 1280
PCA_DIM = 98
MODEL_A_DIM = 1378  # 1280 + 98
MODEL_BC_DIM = 1280

# Colors
COLOR_SHOPLIFT = (60, 80, 255)
COLOR_NORMAL = (80, 220, 100)
COLOR_UNKNOWN = (180, 180, 180)

# Model paths (update these after downloading)
MODEL_DIR = Path("models")
PATH_A = MODEL_DIR / "best_attention_lstm.keras"
PATH_B = MODEL_DIR / "best_model.keras"
PATH_C = MODEL_DIR / "shoplifting_exp_c.keras"

# Global models
yolo_model = None
mobilenet_model = None
pca_model = None
models = {}

def load_models():
    global yolo_model, mobilenet_model, pca_model, models

    if yolo_model is not None:
        return  # Already loaded

    print("Loading models...")

    # Check model files exist
    for path in [PATH_A, PATH_B, PATH_C]:
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

    yolo_model = YOLO("yolo11n.pt")
    print("YOLO loaded")

    base = MobileNetV2(weights="imagenet", include_top=False, input_shape=(224, 224, 3), pooling="avg")
    mobilenet_model = tf.keras.Model(inputs=base.input, outputs=base.output)
    mobilenet_model.trainable = False
    print("MobileNetV2 loaded")

    # Fit PCA with dummy data (replace with real fitted PCA if available)
    rng = np.random.RandomState(42)
    fake = rng.randn(500, 1280).astype(np.float32)
    pca_model = PCA(n_components=PCA_DIM, random_state=42)
    pca_model.fit(fake)
    print("PCA fitted")

    models["A"] = load_model(PATH_A)
    models["B"] = load_model(PATH_B)
    models["C"] = load_model(PATH_C)
    print("Keras models loaded")

# Helper functions
def crop_person(frame_bgr, box):
    h, w = frame_bgr.shape[:2]
    x1, y1, x2, y2 = box
    px = (x2 - x1) * CROP_PADDING
    py = (y2 - y1) * CROP_PADDING
    x1 = max(0, int(x1 - px))
    y1 = max(0, int(y1 - py))
    x2 = min(w, int(x2 + px))
    y2 = min(h, int(y2 + py))
    crop = frame_bgr[y1:y2, x1:x2]
    if crop.size == 0:
        crop = frame_bgr
    return cv2.cvtColor(cv2.resize(crop, (224, 224)), cv2.COLOR_BGR2RGB)

def mobilenet_feat(crop_rgb):
    x = preprocess_input(np.expand_dims(crop_rgb.astype(np.float32), 0))
    return mobilenet_model.predict(x, verbose=0).flatten()

def optical_flow_feat(prev_gray, curr_gray):
    flow = cv2.calcOpticalFlowFarneback(
        prev_gray, curr_gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)
    flat = flow.flatten().astype(np.float32)
    flat = flat[:1280] if flat.shape[0] >= 1280 else np.pad(flat, (0, 1280 - flat.shape[0]))
    return pca_model.transform(flat.reshape(1, -1))[0].astype(np.float32)

def predict_window(window, model_key):
    dim = MODEL_A_DIM if model_key == "A" else MODEL_BC_DIM
    x = np.array(window, dtype=np.float32).reshape(1, WINDOW_SIZE, dim)

    if model_key == "C":
        out = models[model_key](x)
        if hasattr(out, "values"):  # dict-like
            prob = float(list(out.values())[0].numpy().flatten()[0])
        else:  # plain tensor
            prob = float(out.numpy().flatten()[0])
    else:
        prob = float(models[model_key].predict(x, verbose=0)[0][0])

    label = "Shoplifting" if prob >= THRESHOLDS[model_key] else "Normal"
    return label, round(prob, 6)

def annotate_frame(frame, track_id, box, label, prob, model_key):
    x1, y1, x2, y2 = map(int, box)
    color = COLOR_SHOPLIFT if label == "Shoplifting" else (COLOR_NORMAL if label == "Normal" else COLOR_UNKNOWN)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    tag = f"ID:{track_id} {label} {prob:.4f}"
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
    ty = max(y1 - 6, th + 4)
    cv2.rectangle(frame, (x1, ty - th - 6), (x1 + tw + 8, ty + 2), (10, 10, 10), -1)
    cv2.putText(frame, tag, (x1 + 4, ty - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    return frame

def draw_hud(frame, model_key, frame_idx, active_tracks):
    lines = [
        f"Model {model_key}",
        f"Threshold: {THRESHOLDS[model_key]}",
        f"Frame: {frame_idx}",
        f"Active persons: {active_tracks}",
    ]
    y = 18
    for line in lines:
        (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
        cv2.rectangle(frame, (6, y - th - 4), (14 + tw, y + 4), (20, 20, 20), -1)
        cv2.putText(frame, line, (10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, (220, 220, 220), 1, cv2.LINE_AA)
        y += 22

# Main inference function
def process_video_local(video_path, model_key):
    load_models()  # Ensure models are loaded

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_name = os.path.basename(video_path)

    track_windows = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    track_labels = defaultdict(lambda: ("Pending", 0.0))
    track_prev_gray = {}
    logged_tracks = set()

    incidents = []
    frame_idx = 0
    summary_frames = []
    total_frames = max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        results = yolo_model.track(
            frame, classes=[0], conf=YOLO_CONF,
            tracker="bytetrack.yaml", persist=True, verbose=False,
        )

        boxes_data = []
        if results[0].boxes is not None and results[0].boxes.id is not None:
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy()
            for tid, box in zip(ids, boxes):
                boxes_data.append((int(tid), box))

        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        for track_id, box in boxes_data:
            crop_rgb = crop_person(frame, box)
            mn_feat = mobilenet_feat(crop_rgb)

            if model_key == "A":
                pg = track_prev_gray.get(track_id)
                of_feat = optical_flow_feat(pg, curr_gray) if pg is not None else np.zeros(PCA_DIM, dtype=np.float32)
                feat = np.concatenate([mn_feat, of_feat])
            else:
                feat = mn_feat

            track_windows[track_id].append(feat)
            track_prev_gray[track_id] = curr_gray.copy()

            if len(track_windows[track_id]) == WINDOW_SIZE:
                label, prob = predict_window(track_windows[track_id], model_key)
                track_labels[track_id] = (label, prob)
                if label == "Shoplifting" and track_id not in logged_tracks:
                    logged_tracks.add(track_id)
                    # Log incident (simplified, no file writing)
                    record = {
                        "timestamp_utc": datetime.utcnow().isoformat(),
                        "video": video_name,
                        "frame_index": frame_idx,
                        "track_id": track_id,
                        "model": model_key,
                        "probability": prob,
                        "threshold": THRESHOLDS[model_key],
                    }
                    incidents.append(record)

            label, prob = track_labels[track_id]
            annotate_frame(frame, track_id, box, label, prob, model_key)

        draw_hud(frame, model_key, frame_idx, len(boxes_data))

        # Summary frame every 1/8 of video
        if frame_idx % max(1, total_frames // 8) == 0:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            summary_frames.append(base64.b64encode(buf).decode())

    cap.release()

    return {
        "model": model_key,
        "threshold": THRESHOLDS[model_key],
        "total_frames": frame_idx,
        "unique_tracks": len(track_labels),
        "shoplifting_tracks": sum(1 for l, _ in track_labels.values() if l == "Shoplifting"),
        "inference_seconds": 0.0,  # Placeholder, can add timing
        "incidents": incidents,
        "summary_frames": summary_frames,
    }

def stream_video_inference(video_path, model_key):
    """Generator for streaming annotated frames as NDJSON."""
    load_models()

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        yield json.dumps({"type": "error", "message": "Cannot open video"}) + "\n"
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    video_name = os.path.basename(video_path)

    track_windows = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    track_labels = defaultdict(lambda: ("Pending", 0.0))
    track_prev_gray = {}
    logged_tracks = set()
    frame_idx = 0

    # Send metadata first
    yield json.dumps({
        "type": "meta",
        "fps": fps,
        "total": total,
        "model": model_key,
    }) + "\n"

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        results = yolo_model.track(
            frame, classes=[0], conf=YOLO_CONF,
            tracker="bytetrack.yaml", persist=True, verbose=False,
        )

        boxes_data = []
        if results[0].boxes is not None and results[0].boxes.id is not None:
            ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy()
            for tid, box in zip(ids, boxes):
                boxes_data.append((int(tid), box))

        curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        incidents_this_frame = []

        for track_id, box in boxes_data:
            crop_rgb = crop_person(frame, box)
            mn_feat = mobilenet_feat(crop_rgb)

            if model_key == "A":
                pg = track_prev_gray.get(track_id)
                of_feat = optical_flow_feat(pg, curr_gray) if pg is not None else np.zeros(PCA_DIM, dtype=np.float32)
                feat = np.concatenate([mn_feat, of_feat])
            else:
                feat = mn_feat

            track_windows[track_id].append(feat)
            track_prev_gray[track_id] = curr_gray.copy()

            if len(track_windows[track_id]) == WINDOW_SIZE:
                label, prob = predict_window(track_windows[track_id], model_key)
                track_labels[track_id] = (label, prob)

                if label == "Shoplifting" and track_id not in logged_tracks:
                    logged_tracks.add(track_id)
                    record = {
                        "timestamp_utc": datetime.utcnow().isoformat(),
                        "video": video_name,
                        "frame_index": frame_idx,
                        "track_id": track_id,
                        "model": model_key,
                        "probability": prob,
                        "threshold": THRESHOLDS[model_key],
                    }
                    incidents_this_frame.append(record)

            label, prob = track_labels[track_id]
            annotate_frame(frame, track_id, box, label, prob, model_key)

        draw_hud(frame, model_key, frame_idx, len(boxes_data))

        # Encode annotated frame as JPEG → base64
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        b64 = base64.b64encode(buf).decode()

        payload = {
            "type": "frame",
            "frame": b64,
            "frame_idx": frame_idx,
            "total": total,
            "incidents": incidents_this_frame,
        }
        yield json.dumps(payload) + "\n"

    cap.release()
    yield json.dumps({"type": "done", "total_frames": frame_idx}) + "\n"