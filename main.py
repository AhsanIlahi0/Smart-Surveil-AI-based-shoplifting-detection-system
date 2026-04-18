"""
main.py  —  FYP Shoplifting Detection Backend
----------------------------------------------
Runs locally on Ubuntu / Arch Linux.
Inference is delegated to a Kaggle kernel via HTTP (ngrok URL).
Results and incidents are persisted in PostgreSQL.
Annotated video is streamed frame-by-frame over WebSocket.
"""

from database import engine, get_db, SessionLocal
import streamer
import models as db_models
import kaggle_client as kc
import asyncio
import base64
import os
import shutil
import threading
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import List
from database import engine, get_db, SessionLocal
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


# ── Create all tables ──────────────────────────────────────────────────────────
db_models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="FYP Shoplifting Detection")
app.mount("/static", StaticFiles(directory="static"), name="static")

UPLOAD_DIR = Path("uploads")
INCIDENT_DIR = Path("incidents")
UPLOAD_DIR.mkdir(exist_ok=True)
INCIDENT_DIR.mkdir(exist_ok=True)


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
        print(f"[JOB] File read — {
              len(video_bytes)} bytes, sending to Kaggle...")

        data = await kc.predict_video(video_bytes, video.filename, model)
        print(f"[JOB] Kaggle responded — keys: {list(data.keys())}")
        result = db_models.InferenceResult(
            video_id=video_id,
            model=data.get("model", model),
            threshold=data.get("threshold"),
            total_frames=data.get("total_frames"),
            unique_tracks=data.get("unique_tracks"),
            shoplifting_tracks=data.get("shoplifting_tracks"),
            inference_seconds=data.get("inference_time_seconds"),
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
        annotated_b64 = data.get("annotated_video_b64", "")
        annotated_path = None
        if annotated_b64:
            annotated_path = str(
                UPLOAD_DIR / f"annotated_{video_id}_{model}.mp4")
            with open(annotated_path, "wb") as f:
                f.write(base64.b64decode(annotated_b64))
            video.annotated_filepath = annotated_path
            print(f"[JOB] Annotated video saved to {annotated_path}")
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
    "model": "B",
    "thread": None,
}


def rtsp_worker(url: str, model: str, loop: asyncio.AbstractEventLoop):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        asyncio.run_coroutine_threadsafe(
            alert_manager.broadcast(
                {"type": "RTSP_ERROR", "error": "Cannot open RTSP stream"}
            ),
            loop,
        )
        rtsp_state["running"] = False
        return

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

        cv2.rectangle(frame, (0, 0), (w, 46), banner_color, -1)
        cv2.putText(
            frame,
            f"  RTSP LIVE  |  {current_label}  |  Confidence {
                current_prob:.1%}  |  Model {model}  |  Frame {frame_count}",
            (8, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.68,
            text_color,
            2,
            cv2.LINE_AA,
        )
        if current_label == "Shoplifting":
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), (40, 40, 200), 8)

        # ── Encode full frame → send to browser ───────────────────────────────
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        full_b64 = base64.b64encode(buf).decode()

        asyncio.run_coroutine_threadsafe(
            alert_manager.broadcast({"type": "FRAME", "frame": full_b64}),
            loop,
        )

        # ── Collect small frames for Kaggle webcam endpoint ───────────────────
        small = cv2.resize(frame, (224, 224))
        _, sbuf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])
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
def dashboard():
    return FileResponse("static/index.html")


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    try:
        kaggle = await kc.health_check()
        return {"local": "ok", "kaggle": kaggle, "kaggle_url": kc.get_kaggle_url()}
    except Exception as e:
        return {
            "local": "ok",
            "kaggle": f"unreachable: {e}",
            "kaggle_url": kc.get_kaggle_url(),
        }


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
    filepath_str = str(dest)
    model_str = model.upper()

    print(f"[UPLOAD] Video #{video_id} saved — launching thread")

    def run_in_thread():
        import asyncio

        print(f"[THREAD] Starting job for video #{video_id}")
        asyncio.run(process_video_job(video_id, filepath_str, model_str))
        print(f"[THREAD] Job done for video #{video_id}")

    threading.Thread(target=run_in_thread, daemon=True).start()

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


# ── RTSP controls ─────────────────────────────────────────────────────────────
@app.post("/api/rtsp/start")
def start_rtsp(url: str = Form(...), model: str = Form(default="B")):
    if rtsp_state["running"]:
        return {"message": "Already running — stop first"}

    rtsp_state["running"] = True
    rtsp_state["url"] = url
    rtsp_state["model"] = model.upper()

    loop = asyncio.get_event_loop()
    thread = threading.Thread(
        target=rtsp_worker, args=(url, model.upper(), loop), daemon=True
    )
    rtsp_state["thread"] = thread
    thread.start()

    return {"ok": True, "url": url, "model": model.upper()}


@app.post("/api/rtsp/stop")
def stop_rtsp():
    rtsp_state["running"] = False
    return {"ok": True}


@app.get("/api/rtsp/status")
def rtsp_status():
    return {
        "running": rtsp_state["running"],
        "url": rtsp_state["url"],
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

    video = db.query(db_models.Video).get(video_id)
    if not video:
        await ws.send_json({"type": "ERROR", "message": "Video not found"})
        await ws.close()
        return

    # Update status
    video.status = "processing"
    db.commit()
    await ws.send_json({"type": "STATUS", "status": "processing"})

    all_incidents = []

    try:
        with open(video.filepath, "rb") as f:
            video_bytes = f.read()

        async def on_frame(payload: dict):
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

        await kc.predict_video_stream(
            video_bytes, video.filename, video.model_used, on_frame
        )

        video.status = "done"
        db.commit()

    except WebSocketDisconnect:
        video.status = "failed"
        db.commit()
    except Exception as e:
        print(f"[WS_INFER] Error: {e}")
        video.status = "failed"
        db.commit()
        try:
            await ws.send_json({"type": "ERROR", "message": str(e)})
        except Exception:
            pass


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
