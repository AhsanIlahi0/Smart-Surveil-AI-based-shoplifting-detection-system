"""
streamer.py
-----------
Reads a locally-saved video file frame by frame, overlays shoplifting annotations
derived from the incidents stored in the database, and streams JPEG frames
over a WebSocket connection so the browser can display a live-annotated playback.

No ML models are loaded here — all inference was already done by Kaggle.
The annotation is purely visual: red banners + bounding-area highlights
are shown for SHOW_DURATION frames after each incident's frame_index.
"""

import asyncio
import base64
import cv2
import numpy as np
from typing import Any


# How many frames to keep the alert overlay visible after the incident frame
SHOW_DURATION = 90   # ~3 s at 30 fps

# BGR colours
RED   = (30,  30,  220)
WHITE = (255, 255, 255)
BLACK = (10,  10,  10)
GREY  = (160, 160, 160)


def _draw_alert_banner(frame: np.ndarray, incidents: list[dict], frame_idx: int) -> np.ndarray:
    """
    Draw a red banner at the top of the frame for each active incident.
    incidents: list of {track_id, probability, model, frame_index}
    """
    h, w = frame.shape[:2]
    banner_h = 44

    for i, inc in enumerate(incidents):
        y0 = i * (banner_h + 2)
        y1 = y0 + banner_h

        # Semi-transparent red overlay
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, y0), (w, y1), (20, 20, 180), -1)
        cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

        text = (
            f"  SHOPLIFTING DETECTED  |  "
            f"Track #{inc['track_id']}  |  "
            f"Confidence {inc['probability']:.1%}  |  "
            f"Model {inc['model']}  |  "
            f"Frame {inc['frame_index']}"
        )
        cv2.putText(
            frame, text,
            (8, y0 + 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.68, WHITE, 2, cv2.LINE_AA,
        )

    return frame


def _draw_hud(frame: np.ndarray, frame_idx: int, total: int, status: str) -> np.ndarray:
    """Bottom-left HUD: frame counter + status."""
    h, w = frame.shape[:2]
    info = f"Frame {frame_idx}/{total}   {status}"
    cv2.rectangle(frame, (0, h - 28), (len(info) * 9 + 10, h), BLACK, -1)
    cv2.putText(frame, info, (6, h - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, GREY, 1, cv2.LINE_AA)
    return frame


async def stream_video(video_path: str, incidents: list[dict], websocket: Any):
    """
    Main coroutine.  Call this from a FastAPI WebSocket handler.

    incidents — list of dicts with keys:
        track_id, frame_index, probability, model
    """

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        await websocket.send_json({"type": "ERROR", "message": "Cannot open video file"})
        return

    fps         = cap.get(cv2.CAP_PROP_FPS) or 25
    total       = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    frame_delay = 1.0 / fps          # target seconds per frame

    # Build a map: frame_index → list of incidents starting at that frame
    trigger_map: dict[int, list[dict]] = {}
    for inc in incidents:
        fi = inc.get("frame_index", 0)
        trigger_map.setdefault(fi, []).append(inc)

    # Active incidents: track_id → {inc_dict, countdown}
    active: dict[int, dict] = {}

    frame_idx = 0

    await websocket.send_json({"type": "START", "fps": fps, "total_frames": total})

    while True:
        t_start = asyncio.get_event_loop().time()

        ret, frame = cap.read()
        if not ret:
            break
        frame_idx += 1

        # Activate new incidents
        for inc in trigger_map.get(frame_idx, []):
            active[inc["track_id"]] = {"inc": inc, "countdown": SHOW_DURATION}

        # Collect currently visible incidents
        visible = [info["inc"] for info in active.values()]

        # Draw overlays
        if visible:
            frame = _draw_alert_banner(frame, visible, frame_idx)

        # Subtle red border when any incident is active
        if visible:
            h, w = frame.shape[:2]
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (40, 40, 200), 8)

        status = f"ALERT x{len(visible)}" if visible else "Normal"
        frame  = _draw_hud(frame, frame_idx, total, status)

        # Decrement countdowns and purge expired
        for tid in list(active.keys()):
            active[tid]["countdown"] -= 1
            if active[tid]["countdown"] <= 0:
                del active[tid]

        # Encode → base64 → send
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 72])
        b64    = base64.b64encode(buf).decode()

        await websocket.send_json({
            "type":      "FRAME",
            "frame":     b64,
            "frame_idx": frame_idx,
            "total":     total,
            "alert":     len(visible) > 0,
        })

        # Pace playback to real-time
        elapsed = asyncio.get_event_loop().time() - t_start
        sleep   = max(0.0, frame_delay - elapsed)
        if sleep > 0:
            await asyncio.sleep(sleep)

    cap.release()
    await websocket.send_json({"type": "END", "total_frames": frame_idx})
