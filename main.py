"""
main.py  —  Smart Surveil Backend
----------------------------------------------
Real-time shoplifting detection system with React frontend.
Uses YOLOv11 and custom models for video analysis.
"""

if __package__:
    from .database import engine, get_db, SessionLocal
    from . import streamer
    from . import models as db_models
    from . import kaggle_client as kc
else:
    from database import engine, get_db, SessionLocal
    import streamer
    import models as db_models
    import kaggle_client as kc
import asyncio
import base64
import httpx
import importlib
import json
import os
import shutil
import threading
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import List
import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

load_dotenv()


_inference_module = None
_inference_import_error = None


def local_inference_enabled() -> bool:
    return os.getenv("ENABLE_LOCAL_INFERENCE", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def local_inference_usable() -> bool:
    return local_inference_enabled() and _inference_import_error is None


def get_inference_module():
    """Load heavy inference deps only when needed so API can start without TensorFlow."""
    global _inference_module, _inference_import_error
    if _inference_module is not None:
        return _inference_module

    # If import already failed once in this process, avoid repeating noisy TensorFlow DLL errors.
    if _inference_import_error is not None:
        raise RuntimeError(_inference_import_error)

    module_name = f"{__package__}.inference" if __package__ else "inference"
    try:
        _inference_module = importlib.import_module(module_name)
        return _inference_module
    except Exception as exc:
        _inference_import_error = f"Local inference import failed: {exc}"
        raise RuntimeError(_inference_import_error) from exc


# ── Create all tables ──────────────────────────────────────────────────────────
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Smart Surveil - Real-time Shoplifting Detection")

FRONTEND_DIST = Path("frontend") / "dist"

UPLOAD_DIR = Path("uploads")
INCIDENT_DIR = Path("incidents")
ANNOTATED_DIR = Path("annotated_videos")
UPLOAD_DIR.mkdir(exist_ok=True)
INCIDENT_DIR.mkdir(exist_ok=True)
ANNOTATED_DIR.mkdir(exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket connection manager
# ══════════════════════════════════════════════════════════════════════════════


class ConnectionManager:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.clients: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self.clients:
                self.clients.remove(ws)

    async def broadcast(self, payload: dict):
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)


alert_manager = ConnectionManager()


# ══════════════════════════════════════════════════════════════════════════════
# Background job: send video to Kaggle, store results
# ══════════════════════════════════════════════════════════════════════════════


async def process_video_job(video_id: int, filepath: str, model: str):
    print(f"[JOB] ▶ Started video_id={video_id} model={model}")
    db = SessionLocal()
    stop_event = get_video_stop_event(video_id)
    try:
        video = db.query(db_models.Video).get(video_id)
        video.status = "processing"
        db.commit()
        print(f"[JOB] DB updated to processing")

        await alert_manager.broadcast(
            {"type": "STATUS", "video_id": video_id, "status": "processing"}
        )
        print(f"[JOB] Broadcast sent")

        with open(filepath, "rb") as f:
            video_bytes = f.read()
        print(f"[JOB] File read — {len(video_bytes)} bytes")

        data = None
        if local_inference_usable():
            try:
                print("[JOB] Running local inference...")
                inference_module = get_inference_module()
                
                # Create output video path for annotated result
                video_filename = Path(filepath).stem
                output_video_path = ANNOTATED_DIR / f"{video_filename}_annotated_model{model}.mp4"
                
                data = inference_module.process_video_local(
                    filepath,
                    model,
                    alert_manager,
                    video_id,
                    asyncio.get_running_loop(),
                    should_stop=stop_event.is_set,
                    output_video_path=str(output_video_path),
                )
                print(f"[JOB] Local inference completed — keys: {list(data.keys())}")
            except Exception as local_exc:
                print(f"[JOB] Local inference failed: {local_exc}")

        if data is not None and data.get("cancelled"):
            video.status = "stopped"
            db.commit()
            await alert_manager.broadcast(
                {"type": "STATUS", "video_id": video_id, "status": "stopped"}
            )
            return

        if stop_event.is_set():
            video.status = "stopped"
            # Clean up partial annotated video if it exists
            if data and data.get("output_video_path"):
                try:
                    Path(data.get("output_video_path")).unlink(missing_ok=True)
                except Exception:
                    pass
            db.commit()
            await alert_manager.broadcast(
                {"type": "STATUS", "video_id": video_id, "status": "stopped"}
            )
            return

        if data is None:
            kaggle_url = kc.get_kaggle_url()
            if not kaggle_url:
                msg = (
                    "Inference unavailable: set KAGGLE_URL or enable local inference "
                    "with ENABLE_LOCAL_INFERENCE=true."
                )
                print(f"[JOB] {msg}")
                video.status = "failed"
                db.commit()
                await alert_manager.broadcast(
                    {
                        "type": "STATUS",
                        "video_id": video_id,
                        "status": "failed",
                        "error": msg,
                    }
                )
                return

            print(f"[JOB] Using Kaggle inference: {kaggle_url}")
            data = await kc.predict_video(video_bytes, Path(filepath).name, model)
            print(f"[JOB] Kaggle inference completed — keys: {list(data.keys())}")

        result = db_models.InferenceResult(
            video_id=video_id,
            model=data.get("model", model),
            threshold=data.get("threshold"),
            total_frames=data.get("total_frames"),
            unique_tracks=data.get("unique_tracks"),
            shoplifting_tracks=data.get("shoplifting_tracks"),
            inference_seconds=data.get("inference_seconds", data.get("inference_time_seconds")),
        )
        db.add(result)
        db.flush()

        summary_frames = data.get("summary_frames", [])
        kaggle_incidents = data.get("incidents", [])

        for i, inc in enumerate(kaggle_incidents):
            snap = (
                summary_frames[min(i, len(summary_frames) - 1)]
                if summary_frames
                else ""
            )
            incident = db_models.Incident(
                video_id=video_id,
                result_id=result.id,
                track_id=inc.get("track_id"),
                frame_index=inc.get("frame_index"),
                probability=inc.get("probability"),
                model=inc.get("model", model),
                snapshot_b64=snap,
                detected_at=datetime.utcnow(),
            )
            db.add(incident)

            await alert_manager.broadcast(
                {
                    "type": "ALERT",
                    "video_id": video_id,
                    "track_id": inc.get("track_id"),
                    "probability": inc.get("probability"),
                    "frame_index": inc.get("frame_index"),
                    "model": inc.get("model", model),
                    "snapshot": snap,
                }
            )
        # Store annotated video path from local inference
        if data and data.get("output_video_path"):
            video.annotated_filepath = data.get("output_video_path")
        video.status = "done"
        db.commit()

        await alert_manager.broadcast(
            {
                "type": "STATUS",
                "video_id": video_id,
                "status": "done",
                "shoplifting": data.get("shoplifting_tracks", 0),
                "total_incidents": len(kaggle_incidents),
            }
        )

    except Exception as exc:
        try:
            video = db.query(db_models.Video).get(video_id)
            video.status = "failed"
            db.commit()
        except Exception:
            pass
        await alert_manager.broadcast(
            {
                "type": "STATUS",
                "video_id": video_id,
                "status": "failed",
                "error": str(exc),
            }
        )
        print(f"[ERROR] video_id={video_id}: {exc}")
    finally:
        db.close()


# async def process_video_job(video_id: int, filepath: str, model: str, loop: asyncio.AbstractEventLoop):
#     db = next(get_db())
#     try:
#         # ── Mark as processing ────────────────────────────────────────────────
#         video = db.query(db_models.Video).get(video_id)
#         video.status = "processing"
#         db.commit()
#
#         asyncio.run_coroutine_threadsafe(
#             alert_manager.broadcast({"type": "STATUS", "video_id": video_id, "status": "processing"}),
#             loop,
#         ).result()
#
#         # ── Send to Kaggle ────────────────────────────────────────────────────
#         with open(filepath, "rb") as f:
#             video_bytes = f.read()
#
#         data = await kc.predict_video(video_bytes, video.filename, model)
#
#         # ── Store InferenceResult ─────────────────────────────────────────────
#         result = db_models.InferenceResult(
#             video_id           = video_id,
#             model              = data.get("model", model),
#             threshold          = data.get("threshold"),
#             total_frames       = data.get("total_frames"),
#             unique_tracks      = data.get("unique_tracks"),
#             shoplifting_tracks = data.get("shoplifting_tracks"),
#             inference_seconds  = data.get("inference_time_seconds"),
#         )
#         db.add(result)
#         db.flush()
#
#         # ── Store Incidents ───────────────────────────────────────────────────
#         summary_frames = data.get("summary_frames", [])
#         kaggle_incidents = data.get("incidents", [])
#
#         for i, inc in enumerate(kaggle_incidents):
#             # Use the summary frame closest to this incident as a snapshot
#             snap = summary_frames[min(i, len(summary_frames) - 1)] if summary_frames else ""
#
#             incident = db_models.Incident(
#                 video_id     = video_id,
#                 result_id    = result.id,
#                 track_id     = inc.get("track_id"),
#                 frame_index  = inc.get("frame_index"),
#                 probability  = inc.get("probability"),
#                 model        = inc.get("model", model),
#                 snapshot_b64 = snap,
#                 detected_at  = datetime.utcnow(),
#             )
#             db.add(incident)
#
#             # Push live alert to every connected browser
#             asyncio.run_coroutine_threadsafe(
#                 alert_manager.broadcast({
#                     "type":        "ALERT",
#                     "video_id":    video_id,
#                     "track_id":    inc.get("track_id"),
#                     "probability": inc.get("probability"),
#                     "frame_index": inc.get("frame_index"),
#                     "model":       inc.get("model", model),
#                     "snapshot":    snap,
#                 }),
#                 loop,
#             ).result()
#
#         video.status = "done"
#         db.commit()
#
#         asyncio.run_coroutine_threadsafe(
#             alert_manager.broadcast({
#                 "type":            "STATUS",
#                 "video_id":        video_id,
#                 "status":          "done",
#                 "shoplifting":     data.get("shoplifting_tracks", 0),
#                 "total_incidents": len(kaggle_incidents),
#             }),
#             loop,
#         ).result()
#
#     except Exception as exc:
#         try:
#             video = db.query(db_models.Video).get(video_id)
#             video.status = "failed"
#             db.commit()
#         except Exception:
#             pass
#
#         asyncio.run_coroutine_threadsafe(
#             alert_manager.broadcast({
#                 "type":    "STATUS",
#                 "video_id": video_id,
#                 "status":  "failed",
#                 "error":   str(exc),
#             }),
#             loop,
#         ).result()
#
#         print(f"[ERROR] process_video_job video_id={video_id}: {exc}")
#     finally:
#         db.close()
#

# ══════════════════════════════════════════════════════════════════════════════
# RTSP worker (thread)
# ══════════════════════════════════════════════════════════════════════════════

rtsp_state = {
    "running": False,
    "url": "",
    "source_type": "rtsp",
    "camera_index": 0,
    "model": "B",
    "thread": None,
}

RTSP_FRAME_MAX_WIDTH = 960
RTSP_JPEG_QUALITY = 45


def encode_preview_frame(frame, quality: int = RTSP_JPEG_QUALITY) -> str:
    height, width = frame.shape[:2]
    if width > RTSP_FRAME_MAX_WIDTH:
        scale = RTSP_FRAME_MAX_WIDTH / float(width)
        frame = cv2.resize(frame, (RTSP_FRAME_MAX_WIDTH, max(1, int(height * scale))))

    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode()

video_stop_events: dict[int, threading.Event] = {}
video_stop_lock = threading.Lock()
video_stream_clients: dict[int, set[WebSocket]] = defaultdict(set)
video_stream_clients_lock = asyncio.Lock()


def prepare_video_stop_event(video_id: int) -> threading.Event:
    with video_stop_lock:
        event = video_stop_events.get(video_id)
        if event is None:
            event = threading.Event()
            video_stop_events[video_id] = event
        event.clear()
        return event


def get_video_stop_event(video_id: int) -> threading.Event:
    with video_stop_lock:
        event = video_stop_events.get(video_id)
        if event is None:
            event = threading.Event()
            video_stop_events[video_id] = event
        return event


def request_video_stop(video_id: int) -> None:
    get_video_stop_event(video_id).set()


async def register_video_stream_client(video_id: int, ws: WebSocket) -> None:
    async with video_stream_clients_lock:
        video_stream_clients[video_id].add(ws)


async def unregister_video_stream_client(video_id: int, ws: WebSocket) -> None:
    async with video_stream_clients_lock:
        clients = video_stream_clients.get(video_id)
        if not clients:
            return
        clients.discard(ws)
        if not clients:
            video_stream_clients.pop(video_id, None)


async def get_video_stream_clients(video_id: int) -> list[WebSocket]:
    async with video_stream_clients_lock:
        return list(video_stream_clients.get(video_id, set()))


def rtsp_worker(
    source_type: str,
    source_value,
    model: str,
    loop: asyncio.AbstractEventLoop,
):
    if source_type == "camera":
        try:
            source_index = int(source_value)
        except (TypeError, ValueError):
            source_index = 0
        cap = cv2.VideoCapture(source_index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(source_value)

    if not cap.isOpened():
        message = (
            f"Cannot open device camera {source_value}"
            if source_type == "camera"
            else "Cannot open RTSP stream"
        )
        asyncio.run_coroutine_threadsafe(
            alert_manager.broadcast(
                {"type": "RTSP_ERROR", "error": message}
            ),
            loop,
        )
        rtsp_state["running"] = False
        return

    inference_module = None
    live_state = None

    if local_inference_usable():
        try:
            inference_module = get_inference_module()
            inference_module.load_models()
            live_state = inference_module.create_live_state()
            print("[RTSP] Using local live inference pipeline")
        except Exception as e:
            inference_module = None
            live_state = None
            print(f"[RTSP] Local live inference unavailable, fallback to webcam endpoint: {e}")

    frame_buffer: list[str] = []
    current_label = "Pending"
    current_prob = 0.0
    frame_count = 0

    while rtsp_state["running"]:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        frame_count += 1
        incidents_this_frame = []

        if inference_module and live_state is not None:
            incidents_this_frame, current_label, current_prob = (
                inference_module.infer_and_annotate_live_frame(
                    frame,
                    model,
                    frame_count,
                    live_state,
                    video_name=f"{source_type}:{source_value}",
                )
            )

        h, w = frame.shape[:2]

        # ── Overlay current classification ────────────────────────────────────
        if current_label == "Shoplifting":
            banner_color = (20, 20, 180)
            text_color = (255, 255, 255)
        elif current_label == "Normal":
            banner_color = (20, 120, 40)
            text_color = (255, 255, 255)
        else:
            banner_color = (50, 50, 50)
            text_color = (180, 180, 180)

        overlay = frame.copy()
        cv2.rectangle(overlay, (8, 8), (w - 8, 52), (22, 24, 30), -1)
        frame[:] = cv2.addWeighted(overlay, 0.62, frame, 0.38, 0)
        cv2.line(frame, (8, 8), (w - 8, 8), banner_color, 3, cv2.LINE_AA)
        cv2.rectangle(frame, (8, 8), (w - 8, 52), (90, 96, 108), 1)
        cv2.putText(
            frame,
            (
                f"  {source_type.upper()} LIVE  |  {current_label}  |  "
                f"Confidence {current_prob:.1%}  |  Model {model}  |  "
                f"Frame {frame_count}"
            ),
            (16, 38),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.64,
            text_color,
            1,
            cv2.LINE_AA,
        )
        if current_label == "Shoplifting":
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (40, 40, 200), 8)

        # ── Encode full frame → send to browser ───────────────────────────────
        full_b64 = encode_preview_frame(frame)

        asyncio.run_coroutine_threadsafe(
            alert_manager.broadcast(
                {
                    "type": "FRAME",
                    "frame": full_b64,
                    "source": "rtsp",
                    "model": model,
                    "frame_idx": frame_count,
                }
            ),
            loop,
        )

        if inference_module is not None and incidents_this_frame:
            for inc in incidents_this_frame:
                asyncio.run_coroutine_threadsafe(
                    alert_manager.broadcast(
                        {
                            "type": "ALERT",
                            "video_id": None,
                            "source": "rtsp",
                            "track_id": inc.get("track_id"),
                            "probability": inc.get("probability", 0.0),
                            "frame_index": inc.get("frame_index"),
                            "model": model,
                            "snapshot": full_b64,
                        }
                    ),
                    loop,
                )

        if inference_module is None:
            # ── Fallback: webcam classification endpoint ───────────────────────
            small = cv2.resize(frame, (224, 224))
            _, sbuf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
            frame_buffer.append(base64.b64encode(sbuf).decode())

            if len(frame_buffer) == 16:
                try:
                    result = asyncio.run_coroutine_threadsafe(
                        kc.predict_webcam_frames(frame_buffer, model), loop
                    ).result(timeout=25)

                    current_label = result.get("label", "Normal")
                    current_prob = result.get("probability", 0.0)

                    if current_label == "Shoplifting":
                        asyncio.run_coroutine_threadsafe(
                            alert_manager.broadcast(
                                {
                                    "type": "ALERT",
                                    "video_id": None,
                                    "source": "rtsp",
                                    "track_id": "live",
                                    "probability": current_prob,
                                    "frame_index": frame_count,
                                    "model": model,
                                    "snapshot": full_b64,
                                }
                            ),
                            loop,
                        )
                except Exception as e:
                    print(f"[RTSP] Kaggle webcam error: {e}")

                frame_buffer.clear()

        # ~25 fps cap (40 ms)
        time.sleep(0.04)

    cap.release()
    asyncio.run_coroutine_threadsafe(
        alert_manager.broadcast({"type": "RTSP_STOPPED"}), loop
    )


# ══════════════════════════════════════════════════════════════════════════════
# REST endpoints
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    if FRONTEND_DIST.exists():
        return FileResponse(FRONTEND_DIST / "index.html")

    # Serve the React app from dev server
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get('http://localhost:3000')
            return response.text
    except:
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Surveil</title>
</head>
<body>
    <h1>Smart Surveil Backend Running</h1>
    <p>React frontend not available. Start with: cd frontend && npx vite dev --host 0.0.0.0 --port 3000</p>
    <p><a href="/api/docs">API Documentation</a></p>
</body>
</html>
        """


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    if not local_inference_enabled():
        return {
            "local": "disabled",
            "note": "Set ENABLE_LOCAL_INFERENCE=true to enable TensorFlow local inference.",
            "kaggle_url": kc.get_kaggle_url() or "not_set",
        }

    if _inference_import_error is not None:
        return {
            "local": "error",
            "reason": _inference_import_error,
            "kaggle_url": kc.get_kaggle_url() or "not_set",
        }

    try:
        # Check if models are loaded
        inference_module = get_inference_module()
        inference_module.load_models()
        local_status = {
            "models_loaded": list(inference_module.models.keys()),
            "yolo_loaded": inference_module.yolo_model is not None,
            "mobilenet_loaded": inference_module.mobilenet_model is not None,
        }
        return {"local": "ok", "models": local_status}
    except Exception as e:
        return {"local": f"error: {e}"}


# ── Update Kaggle URL at runtime (no restart needed) ───────────────────────────
@app.post("/api/kaggle-url")
async def update_kaggle_url(url: str = Form(...)):
    kc.set_kaggle_url(url)
    return {"ok": True, "url": url}


# ── Video upload ───────────────────────────────────────────────────────────────
@app.post("/api/videos/upload")
async def upload_video(
    video: UploadFile = File(...),
    model: str = Form(default="B"),
    db: Session = Depends(get_db),
):
    if (not local_inference_usable()) and (not kc.get_kaggle_url()):
        reason = _inference_import_error or "Local inference unavailable"
        raise HTTPException(
            status_code=503,
            detail=(
                "Inference unavailable. Set KAGGLE_URL (or update it from dashboard) "
                f"or fix local inference. Reason: {reason}"
            ),
        )

    dest = UPLOAD_DIR / video.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(video.file, f)

    db_video = db_models.Video(
        filename=video.filename,
        filepath=str(dest),
        status="pending",
        source_type="upload",
        model_used=model.upper(),
    )
    db.add(db_video)
    db.commit()
    db.refresh(db_video)

    video_id = db_video.id
    prepare_video_stop_event(video_id)
    print(f"[UPLOAD] Video #{video_id} saved — waiting for live inference websocket")

    return {"video_id": video_id, "status": "pending"}


# @app.post("/api/videos/upload")
# async def upload_video(
#     video: UploadFile = File(...),
#     model: str = Form(default="B"),
#     db: Session = Depends(get_db),
# ):
#     dest = UPLOAD_DIR / video.filename
#     with open(dest, "wb") as f:
#         shutil.copyfileobj(video.file, f)
#
#     db_video = db_models.Video(
#         filename=video.filename,
#         filepath=str(dest),
#         status="pending",
#         source_type="upload",
#         model_used=model.upper(),
#     )
#     db.add(db_video)
#     db.commit()
#     db.refresh(db_video)
#
#     loop = asyncio.get_event_loop()
#     # background_tasks.add_task(
#     #     asyncio.run_coroutine_threadsafe,
#     #     process_video_job(db_video.id, str(dest), model.upper(), loop),
#     #     loop,
#     # )
#
#     return {"video_id": db_video.id, "status": "pending"}


# ── Video list ─────────────────────────────────────────────────────────────────
@app.get("/api/videos")
def list_videos(db: Session = Depends(get_db)):
    rows = db.query(db_models.Video).order_by(
        db_models.Video.created_at.desc()).all()
    return [
        {
            "id": v.id,
            "filename": v.filename,
            "status": v.status,
            "model": v.model_used,
            "source": v.source_type,
            "created_at": v.created_at.isoformat(),
            "incidents": len(v.incidents),
        }
        for v in rows
    ]


# ── Single video detail ────────────────────────────────────────────────────────
@app.get("/api/videos/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(db_models.Video).get(video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    return {
        "id": v.id,
        "filename": v.filename,
        "status": v.status,
        "model": v.model_used,
        "created_at": v.created_at.isoformat(),
        "has_annotated_video": v.annotated_filepath is not None and Path(v.annotated_filepath).exists(),
        "annotated_filename": Path(v.annotated_filepath).name if v.annotated_filepath else None,
        "results": [
            {
                "model": r.model,
                "threshold": r.threshold,
                "total_frames": r.total_frames,
                "unique_tracks": r.unique_tracks,
                "shoplifting_tracks": r.shoplifting_tracks,
                "inference_seconds": r.inference_seconds,
            }
            for r in v.results
        ],
        "incidents": [
            {
                "id": i.id,
                "track_id": i.track_id,
                "frame_index": i.frame_index,
                "probability": i.probability,
                "model": i.model,
                "snapshot": i.snapshot_b64,
                "detected_at": i.detected_at.isoformat(),
            }
            for i in v.incidents
        ],
    }


# ── Download annotated video ──────────────────────────────────────────────────
@app.get("/api/videos/{video_id}/download")
def download_video(video_id: int, db: Session = Depends(get_db)):
    v = db.query(db_models.Video).get(video_id)
    if not v:
        raise HTTPException(404, "Video not found")
    
    if not v.annotated_filepath or not Path(v.annotated_filepath).exists():
        raise HTTPException(404, "Annotated video not available")
    
    video_path = Path(v.annotated_filepath)
    return FileResponse(
        path=video_path,
        media_type="video/mp4",
        filename=video_path.name,
    )


# ── RTSP controls ─────────────────────────────────────────────────────────────
@app.post("/api/rtsp/start")
async def start_rtsp(
    source_type: str = Form(default="rtsp"),
    url: str = Form(default=""),
    camera_index: int = Form(default=0),
    model: str = Form(default="B"),
):
    if rtsp_state["running"]:
        return {"message": "Already running — stop first"}

    source_type = source_type.lower().strip()
    if source_type not in {"rtsp", "camera"}:
        raise HTTPException(400, "source_type must be rtsp or camera")

    if source_type == "rtsp" and not url.strip():
        raise HTTPException(400, "RTSP URL is required")

    rtsp_state["running"] = True
    rtsp_state["url"] = url.strip()
    rtsp_state["source_type"] = source_type
    rtsp_state["camera_index"] = camera_index
    rtsp_state["model"] = model.upper()

    loop = asyncio.get_running_loop()
    thread = threading.Thread(
        target=rtsp_worker,
        args=(source_type, camera_index if source_type == "camera" else url.strip(), model.upper(), loop),
        daemon=True,
    )
    rtsp_state["thread"] = thread
    thread.start()

    return {
        "ok": True,
        "source_type": source_type,
        "url": url.strip(),
        "camera_index": camera_index,
        "model": model.upper(),
    }


@app.post("/api/rtsp/stop")
def stop_rtsp():
    rtsp_state["running"] = False
    return {"ok": True}


@app.post("/api/videos/{video_id}/stop")
async def stop_video_processing(video_id: int, db: Session = Depends(get_db)):
    video = db.query(db_models.Video).get(video_id)
    if not video:
        raise HTTPException(404, "Video not found")

    request_video_stop(video_id)

    if video.status in {"pending", "processing"}:
        video.status = "stopped"
        db.commit()

    await alert_manager.broadcast(
        {"type": "STATUS", "video_id": video_id, "status": "stopped"}
    )

    # Force-close active infer sockets so streaming halts immediately on backend.
    sockets = await get_video_stream_clients(video_id)
    for ws in sockets:
        try:
            await ws.close(code=1000, reason="Stopped by user")
        except Exception:
            pass

    return {"ok": True, "video_id": video_id, "status": "stopping"}


@app.get("/api/rtsp/status")
def rtsp_status():
    return {
        "running": rtsp_state["running"],
        "url": rtsp_state["url"],
        "source_type": rtsp_state["source_type"],
        "camera_index": rtsp_state["camera_index"],
        "model": rtsp_state["model"],
    }


# ── Stats ──────────────────────────────────────────────────────────────────────
@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    all_incidents = db.query(db_models.Incident).all()
    today = date.today()
    today_inc = [i for i in all_incidents if i.detected_at.date() == today]

    # Hourly breakdown today
    hourly: dict[int, int] = defaultdict(int)
    for i in today_inc:
        hourly[i.detected_at.hour] += 1

    avg = sum(hourly.values()) / max(len(hourly), 1)
    high_risk = sorted([h for h, c in hourly.items() if c > avg * 1.2])

    # Daily last 7 days
    daily: dict[str, int] = defaultdict(int)
    for i in all_incidents:
        daily[i.detected_at.date().isoformat()] += 1

    return {
        "today_total": len(today_inc),
        "this_hour": hourly.get(datetime.utcnow().hour, 0),
        "high_risk_hours": high_risk,
        "hourly_today": [{"hour": h, "count": c} for h, c in sorted(hourly.items())],
        "daily_last_7": [
            {"date": d, "count": c} for d, c in sorted(daily.items())[-7:]
        ],
        "total_all_time": len(all_incidents),
    }


# ── Incident log ───────────────────────────────────────────────────────────────
@app.get("/api/incidents")
def get_incidents(limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(db_models.Incident)
        .order_by(db_models.Incident.detected_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": i.id,
            "video_id": i.video_id,
            "track_id": i.track_id,
            "probability": i.probability,
            "model": i.model,
            "frame_index": i.frame_index,
            "detected_at": i.detected_at.isoformat(),
            "snapshot": i.snapshot_b64,
        }
        for i in rows
    ]


@app.delete("/api/incidents/{incident_id}")
def delete_incident(incident_id: int, db: Session = Depends(get_db)):
    i = db.query(db_models.Incident).get(incident_id)
    if not i:
        raise HTTPException(404, "Incident not found")
    db.delete(i)
    db.commit()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket — alerts + RTSP frame broadcast
# ══════════════════════════════════════════════════════════════════════════════


@app.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket):
    await alert_manager.connect(ws)
    try:
        while True:
            # Keep-alive ping from browser; we don't need the data
            await ws.receive_text()
    except WebSocketDisconnect:
        await alert_manager.disconnect(ws)
    except Exception:
        await alert_manager.disconnect(ws)


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket — per-video annotated playback stream
# ══════════════════════════════════════════════════════════════════════════════


# @app.websocket("/ws/stream/{video_id}")
# async def ws_stream(ws: WebSocket, video_id: int, db: Session = Depends(get_db)):
#     video = db.query(db_models.Video).get(video_id)
#     if not video:
#         await ws.accept()
#         await ws.send_json({"type": "ERROR", "message": "Video not found"})
#         await ws.close()
#         return
#
#     if video.status != "done":
#         await ws.accept()
#         await ws.send_json(
#             {"type": "ERROR", "message": f"Video status is '{video.status}'"}
#         )
#         await ws.close()
#         return
#
#     # ── Use Kaggle's annotated video if available, else fall back to original ──
#     play_path = video.annotated_filepath or video.filepath
#     print(
#         f"[STREAM] Streaming {
#             'annotated' if video.annotated_filepath else 'original'
#         } video: {play_path}"
#     )
#
#     # No need to overlay incidents if already annotated by Kaggle
#     incidents = (
#         []
#         if video.annotated_filepath
#         else [
#             {
#                 "track_id": i.track_id,
#                 "frame_index": i.frame_index,
#                 "probability": i.probability,
#                 "model": i.model,
#             }
#             for i in video.incidents
#         ]
#     )
#
#     await ws.accept()
#     try:
#         await streamer.stream_video(play_path, incidents, ws)
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         try:
#             await ws.send_json({"type": "ERROR", "message": str(e)})
#         except Exception:
#             pass
#
@app.websocket("/ws/infer/{video_id}")
async def ws_infer(ws: WebSocket, video_id: int, db: Session = Depends(get_db)):
    """
    Real-time inference stream:
    Sends video to Kaggle, relays annotated frames to browser as they arrive.
    """
    await ws.accept()
    await register_video_stream_client(video_id, ws)

    video = db.query(db_models.Video).get(video_id)
    if not video:
        await ws.send_json({"type": "ERROR", "message": "Video not found"})
        await ws.close()
        return

    stop_event = prepare_video_stop_event(video_id)

    # Update status
    video.status = "processing"
    db.commit()
    await ws.send_json({"type": "STATUS", "status": "processing"})
    await alert_manager.broadcast(
        {"type": "STATUS", "video_id": video_id, "status": "processing"}
    )

    all_incidents = []

    try:
        with open(video.filepath, "rb") as f:
            video_bytes = f.read()

        async def on_frame(payload: dict):
            if stop_event.is_set():
                raise asyncio.CancelledError()

            # Relay every frame straight to browser
            await ws.send_json(payload)

            # If incident in this frame — save to DB immediately
            for inc in payload.get("incidents", []):
                incident = db_models.Incident(
                    video_id=video_id,
                    result_id=None,
                    track_id=inc.get("track_id"),
                    frame_index=inc.get("frame_index"),
                    probability=inc.get("probability"),
                    model=inc.get("model"),
                    detected_at=datetime.utcnow(),
                )
                db.add(incident)
                db.commit()
                all_incidents.append(inc)

                # Also push alert to all other connected dashboards
                await alert_manager.broadcast(
                    {
                        "type": "ALERT",
                        "video_id": video_id,
                        "track_id": inc.get("track_id"),
                        "probability": inc.get("probability"),
                        "frame_index": inc.get("frame_index"),
                        "model": inc.get("model"),
                        "snapshot": payload.get("frame", ""),
                    }
                )

        if local_inference_usable():
            try:
                inference_module = get_inference_module()

                # Use local streaming
                for line in inference_module.stream_video_inference(
                    video.filepath,
                    video.model_used,
                    should_stop=stop_event.is_set,
                ):
                    payload = json.loads(line.strip())
                    if payload.get("type") == "stopped":
                        raise asyncio.CancelledError()
                    await on_frame(payload)
            except (asyncio.CancelledError, WebSocketDisconnect):
                raise
            except Exception as local_exc:
                print(f"[WS_INFER] Local stream failed: {local_exc}")
                kaggle_url = kc.get_kaggle_url()
                if not kaggle_url:
                    reason = _inference_import_error or "Local inference unavailable"
                    msg = (
                        "Inference unavailable: set KAGGLE_URL or enable local inference "
                        f"with ENABLE_LOCAL_INFERENCE=true. Reason: {reason}"
                    )
                    video.status = "failed"
                    db.commit()
                    await ws.send_json({"type": "ERROR", "message": msg})
                    await alert_manager.broadcast(
                        {
                            "type": "STATUS",
                            "video_id": video_id,
                            "status": "failed",
                            "error": msg,
                        }
                    )
                    return

                print(f"[WS_INFER] Falling back to Kaggle: {kaggle_url}")
                await ws.send_json({"type": "STATUS", "status": "fallback_kaggle"})
                await kc.predict_video_stream(
                    video_bytes,
                    video.filename,
                    video.model_used,
                    on_frame,
                    should_stop=stop_event.is_set,
                )
        else:
            kaggle_url = kc.get_kaggle_url()
            if not kaggle_url:
                reason = _inference_import_error or "Local inference unavailable"
                msg = (
                    "Inference unavailable: set KAGGLE_URL or enable local inference "
                    f"with ENABLE_LOCAL_INFERENCE=true. Reason: {reason}"
                )
                video.status = "failed"
                db.commit()
                await ws.send_json({"type": "ERROR", "message": msg})
                await alert_manager.broadcast(
                    {
                        "type": "STATUS",
                        "video_id": video_id,
                        "status": "failed",
                        "error": msg,
                    }
                )
                return

            await ws.send_json({"type": "STATUS", "status": "kaggle_only"})
            await kc.predict_video_stream(
                video_bytes,
                video.filename,
                video.model_used,
                on_frame,
                should_stop=stop_event.is_set,
            )

        if stop_event.is_set():
            raise asyncio.CancelledError()

        video.status = "done"
        db.commit()
        await ws.send_json({"type": "STATUS", "status": "done"})
        await ws.send_json({"type": "done"})
        await alert_manager.broadcast(
            {"type": "STATUS", "video_id": video_id, "status": "done"}
        )

    except asyncio.CancelledError:
        video.status = "stopped"
        db.commit()
        try:
            await ws.send_json({"type": "STATUS", "status": "stopped"})
        except Exception:
            pass
        await alert_manager.broadcast(
            {"type": "STATUS", "video_id": video_id, "status": "stopped"}
        )
    except WebSocketDisconnect:
        video.status = "stopped" if stop_event.is_set() else "failed"
        db.commit()
        await alert_manager.broadcast(
            {
                "type": "STATUS",
                "video_id": video_id,
                "status": video.status,
            }
        )
    except Exception as e:
        print(f"[WS_INFER] Error: {e}")
        video.status = "failed"
        db.commit()
        await alert_manager.broadcast(
            {
                "type": "STATUS",
                "video_id": video_id,
                "status": "failed",
                "error": str(e),
            }
        )
        try:
            await ws.send_json({"type": "ERROR", "message": str(e)})
        except Exception:
            pass
    finally:
        await unregister_video_stream_client(video_id, ws)


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")


# @app.websocket("/ws/stream/{video_id}")
# async def ws_stream(ws: WebSocket, video_id: int, db: Session = Depends(get_db)):
#     """
#     Streams the locally-saved video frame by frame with annotations
#     derived from the incidents stored in PostgreSQL.
#     No ML models are run here — purely visual overlay.
#     """
#     video = db.query(db_models.Video).get(video_id)
#     if not video:
#         await ws.accept()
#         await ws.send_json({"type": "ERROR", "message": "Video not found"})
#         await ws.close()
#         return
#
#     if video.status != "done":
#         await ws.accept()
#         await ws.send_json(
#             {
#                 "type": "ERROR",
#                 "message": f"Video status is '{video.status}' — wait until done",
#             }
#         )
#         await ws.close()
#         return
#
#     incidents = [
#         {
#             "track_id": i.track_id,
#             "frame_index": i.frame_index,
#             "probability": i.probability,
#             "model": i.model,
#         }
#         for i in video.incidents
#     ]
#
#     await ws.accept()
#     try:
#         await streamer.stream_video(video.filepath, incidents, ws)
#     except WebSocketDisconnect:
#         pass
#     except Exception as e:
#         try:
#             await ws.send_json({"type": "ERROR", "message": str(e)})
#         except Exception:
#             pass
