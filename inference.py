"""
inference.py — Local model loading and inference for shoplifting detection.
Adapted from Kaggle kernel code.
"""

import os
import base64
import json
import asyncio
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
FRAME_SKIP = 4  # Stream every 4th frame to keep the dashboard responsive
STREAM_MAX_WIDTH = 960
STREAM_JPEG_QUALITY = 45

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


def invert_labels() -> bool:
    return os.getenv("INVERT_LOCAL_INFERENCE_LABELS", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

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

    is_shoplifting = prob >= THRESHOLDS[model_key]
    if invert_labels():
        is_shoplifting = not is_shoplifting

    label = "Shoplifting" if is_shoplifting else "Normal"
    return label, round(prob, 6)

def annotate_frame(frame, track_id, box, label, prob, model_key):
    x1, y1, x2, y2 = map(int, box)
    color = COLOR_SHOPLIFT if label == "Shoplifting" else (COLOR_NORMAL if label == "Normal" else COLOR_UNKNOWN)
    box_w = max(1, x2 - x1)
    box_h = max(1, y2 - y1)

    # Soft translucent fill inside the box for a modern "glass" effect
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    frame[:] = cv2.addWeighted(overlay, 0.10, frame, 0.90, 0)

    # Main border + corner accents for a cleaner cinematic look
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    corner = max(8, min(box_w, box_h) // 5)
    cv2.line(frame, (x1, y1), (x1 + corner, y1), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x1, y1), (x1, y1 + corner), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x2, y1), (x2 - corner, y1), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x2, y1), (x2, y1 + corner), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x1, y2), (x1 + corner, y2), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x1, y2), (x1, y2 - corner), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x2, y2), (x2 - corner, y2), color, 3, cv2.LINE_AA)
    cv2.line(frame, (x2, y2), (x2, y2 - corner), color, 3, cv2.LINE_AA)

    # Floating label card
    tag = f"#{track_id}  {label}"
    prob_tag = f"{prob:.1%}"
    (tw, th), _ = cv2.getTextSize(tag, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    (pw, _), _ = cv2.getTextSize(prob_tag, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
    card_w = tw + pw + 28
    card_h = th + 12
    card_y2 = y1 - 6 if y1 > (card_h + 10) else y1 + card_h + 6
    card_y1 = card_y2 - card_h
    card_x1 = x1
    card_x2 = x1 + card_w

    overlay = frame.copy()
    cv2.rectangle(overlay, (card_x1, card_y1), (card_x2, card_y2), (22, 24, 30), -1)
    frame[:] = cv2.addWeighted(overlay, 0.72, frame, 0.28, 0)
    cv2.rectangle(frame, (card_x1, card_y1), (card_x2, card_y2), color, 1)

    cv2.putText(frame, tag, (card_x1 + 8, card_y2 - 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (238, 240, 245), 1, cv2.LINE_AA)
    cv2.putText(frame, prob_tag, (card_x2 - pw - 8, card_y2 - 7),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, color, 1, cv2.LINE_AA)

    # Confidence progress bar at the box bottom
    bar_y1 = y2 + 4
    bar_y2 = y2 + 9
    if bar_y2 < frame.shape[0]:
        cv2.rectangle(frame, (x1, bar_y1), (x2, bar_y2), (45, 50, 58), -1)
        fill_x = x1 + int((x2 - x1) * max(0.0, min(1.0, prob)))
        cv2.rectangle(frame, (x1, bar_y1), (fill_x, bar_y2), color, -1)
    return frame

def draw_hud(frame, model_key, frame_idx, active_tracks):
    lines = [
        f"Model {model_key}",
        f"Threshold {THRESHOLDS[model_key]:.2f}",
        f"Frame {frame_idx}",
        f"Tracks {active_tracks}",
    ]

    widths = []
    for line in lines:
        (tw, _), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.53, 1)
        widths.append(tw)

    panel_x1, panel_y1 = 10, 10
    panel_x2 = panel_x1 + max(widths) + 28
    panel_y2 = panel_y1 + 24 * len(lines) + 10

    overlay = frame.copy()
    cv2.rectangle(overlay, (panel_x1, panel_y1), (panel_x2, panel_y2), (18, 20, 26), -1)
    frame[:] = cv2.addWeighted(overlay, 0.60, frame, 0.40, 0)
    cv2.rectangle(frame, (panel_x1, panel_y1), (panel_x2, panel_y2), (90, 96, 108), 1)

    y = panel_y1 + 20
    for line in lines:
        cv2.putText(frame, line, (panel_x1 + 10, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.53, (232, 236, 242), 1, cv2.LINE_AA)
        y += 24


def create_live_state():
    return {
        "track_windows": defaultdict(lambda: deque(maxlen=WINDOW_SIZE)),
        "track_labels": defaultdict(lambda: ("Pending", 0.0)),
        "track_prev_gray": {},
        "logged_tracks": set(),
    }


def infer_and_annotate_live_frame(frame, model_key, frame_idx, state, video_name="live"):
    """Run the same per-frame pipeline used by uploaded video streaming on a live frame."""
    track_windows = state["track_windows"]
    track_labels = state["track_labels"]
    track_prev_gray = state["track_prev_gray"]
    logged_tracks = state["logged_tracks"]

    results = yolo_model.track(
        frame,
        classes=[0],
        conf=YOLO_CONF,
        tracker="bytetrack.yaml",
        persist=True,
        verbose=False,
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
            of_feat = (
                optical_flow_feat(pg, curr_gray)
                if pg is not None
                else np.zeros(PCA_DIM, dtype=np.float32)
            )
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
                incidents_this_frame.append(
                    {
                        "timestamp_utc": datetime.utcnow().isoformat(),
                        "video": video_name,
                        "frame_index": frame_idx,
                        "track_id": track_id,
                        "model": model_key,
                        "probability": prob,
                        "threshold": THRESHOLDS[model_key],
                    }
                )

        label, prob = track_labels[track_id]
        annotate_frame(frame, track_id, box, label, prob, model_key)

    draw_hud(frame, model_key, frame_idx, len(boxes_data))

    known_labels = [(label, prob) for label, prob in track_labels.values() if label != "Pending"]
    if any(label == "Shoplifting" for label, _ in known_labels):
        probs = [prob for label, prob in known_labels if label == "Shoplifting"]
        return incidents_this_frame, "Shoplifting", max(probs) if probs else 0.0
    if known_labels:
        return incidents_this_frame, "Normal", max(prob for _, prob in known_labels)
    return incidents_this_frame, "Pending", 0.0


def encode_stream_frame(frame, quality=STREAM_JPEG_QUALITY):
    height, width = frame.shape[:2]
    if width > STREAM_MAX_WIDTH:
        scale = STREAM_MAX_WIDTH / float(width)
        frame = cv2.resize(frame, (STREAM_MAX_WIDTH, max(1, int(height * scale))))

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode()

# Main inference function
def process_video_local(
    video_path,
    model_key,
    alert_manager=None,
    video_id=None,
    loop=None,
    should_stop=None,
    output_video_path=None,
):
    load_models()  # Ensure models are loaded

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    video_name = os.path.basename(video_path)

    # Initialize video writer for annotated output if path provided
    out = None
    if output_video_path:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        out = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))

    track_windows = defaultdict(lambda: deque(maxlen=WINDOW_SIZE))
    track_labels = defaultdict(lambda: ("Pending", 0.0))
    track_prev_gray = {}
    logged_tracks = set()

    incidents = []
    frame_idx = 0
    summary_frames = []
    total_frames = max(int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), 1)

    cancelled = False

    while True:
        if should_stop and should_stop():
            cancelled = True
            break

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

        # Write annotated frame to output video
        if out:
            out.write(frame)

        # Broadcast frame for real-time viewing (every Nth frame for speed)
        if alert_manager and video_id and loop and frame_idx % FRAME_SKIP == 0:
            b64_frame = encode_stream_frame(frame)
            asyncio.run_coroutine_threadsafe(
                alert_manager.broadcast({
                    "type": "FRAME",
                    "video_id": video_id,
                    "frame": b64_frame,
                    "frame_idx": frame_idx,
                    "total": total_frames,
                    "alert": any(l == "Shoplifting" for l, _ in track_labels.values())
                }),
                loop
            )

        # Summary frame every 1/8 of video
        if frame_idx % max(1, total_frames // 8) == 0:
            summary_frames.append(encode_stream_frame(frame, quality=70))

    cap.release()
    if out:
        out.release()

    return {
        "cancelled": cancelled,
        "model": model_key,
        "threshold": THRESHOLDS[model_key],
        "total_frames": frame_idx,
        "unique_tracks": len(track_labels),
        "shoplifting_tracks": sum(1 for l, _ in track_labels.values() if l == "Shoplifting"),
        "inference_seconds": 0.0,  # Placeholder, can add timing
        "incidents": incidents,
        "summary_frames": summary_frames,
        "output_video_path": output_video_path,
    }

def stream_video_inference(video_path, model_key, should_stop=None):
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
        if should_stop and should_stop():
            yield json.dumps({"type": "stopped"}) + "\n"
            break

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

        # Only stream every Nth frame to frontend to increase dashboard display speed
        if frame_idx % FRAME_SKIP == 0:
            # Encode annotated frame as JPEG → base64 (reduced quality = faster)
            b64 = encode_stream_frame(frame)

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