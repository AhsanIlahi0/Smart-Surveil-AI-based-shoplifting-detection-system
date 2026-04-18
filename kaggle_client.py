import os
import httpx
import json
from dotenv import load_dotenv

load_dotenv()

# Runtime-mutable so the dashboard can update it without restart
_kaggle_url: str = os.getenv("KAGGLE_URL", "").rstrip("/")


def set_kaggle_url(url: str):
    global _kaggle_url
    _kaggle_url = url.rstrip("/")


def get_kaggle_url() -> str:
    return _kaggle_url


def _headers() -> dict:
    token = os.getenv("INFERENCE_TOKEN", "")
    return {"Authorization": f"Bearer {token}"} if token else {}


async def health_check() -> dict:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{get_kaggle_url()}/health", headers=_headers())
        r.raise_for_status()
        return r.json()


async def predict_video_stream(video_bytes: bytes, filename: str, model: str, on_frame):
    """
    Streams frames from Kaggle as they are processed.
    on_frame(payload_dict) is called for every line received.
    """
    async with httpx.AsyncClient(timeout=600) as client:
        async with client.stream(
            "POST",
            f"{get_kaggle_url()}/predict/stream",
            headers=_headers(),
            files={"video": (filename, video_bytes, "video/mp4")},
            data={"model": model},
        ) as r:
            if not r.is_success:
                raise RuntimeError(f"Stream failed {r.status_code}")
            async for line in r.aiter_lines():
                line = line.strip()
                if line:
                    payload = json.loads(line)
                    await on_frame(payload)


async def predict_video(video_bytes: bytes, filename: str, model: str = "B") -> dict:
    """
    Send a full video file to Kaggle /predict.
    Returns the full result dict with incidents + summary_frames.
    Timeout 10 min — Kaggle can take 2–5 min on a long clip.
    """
    async with httpx.AsyncClient(timeout=600) as client:
        r = await client.post(
            f"{get_kaggle_url()}/predict",
            headers=_headers(),
            files={"video": (filename, video_bytes, "video/mp4")},
            data={"model": model},
        )
        if not r.is_success:
            raise RuntimeError(
                f"Kaggle /predict failed {r.status_code}: {r.text[:500]}"
            )
        return r.json()


async def predict_webcam_frames(frames_b64: list[str], model: str = "B") -> dict:
    """
    Send exactly 16 base64-encoded JPEG frames to Kaggle /predict/webcam.
    Used for RTSP real-time inference.
    Returns label, probability, threshold.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{get_kaggle_url()}/predict/webcam",
            headers=_headers(),
            json={"frames_b64": frames_b64, "model": model},
        )
        if not r.is_success:
            raise RuntimeError(
                f"Kaggle /predict/webcam failed {
                    r.status_code}: {r.text[:300]}"
            )
        return r.json()
