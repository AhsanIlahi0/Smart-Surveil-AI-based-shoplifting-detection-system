import os
from functools import lru_cache
from typing import Tuple

import cv2
import numpy as np
import tensorflow as tf
from tensorflow.keras.applications.efficientnet_v2 import EfficientNetV2B0, preprocess_input

TIME_STEPS = 20
FRAME_HEIGHT = 224
FRAME_WIDTH = 224
CHANNELS = 3


def load_model(model_path: str) -> tf.keras.Model:
    """Load a Keras model from disk."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return tf.keras.models.load_model(model_path)


def _read_frames_uniform(video_path: str, num_frames: int) -> np.ndarray:
    """Read frames from a video by uniform sampling across the clip duration."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Unable to open video: {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    sampled_frames = []

    if total_frames > 0:
        sample_indices = np.linspace(0, max(total_frames - 1, 0), num_frames, dtype=np.int32)
        for idx in sample_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if ok and frame is not None:
                sampled_frames.append(frame)
    else:
        while len(sampled_frames) < num_frames:
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            sampled_frames.append(frame)

    cap.release()

    if not sampled_frames:
        raise ValueError("No frames could be extracted from the provided video.")

    # Pad with the last valid frame if the clip is shorter than expected.
    while len(sampled_frames) < num_frames:
        sampled_frames.append(sampled_frames[-1].copy())

    return np.asarray(sampled_frames[:num_frames])


def _preprocess_frames(frames_bgr: np.ndarray, frame_size: Tuple[int, int]) -> np.ndarray:
    """Convert BGR->RGB, resize, and normalize into [0, 1]."""
    processed = []
    target_h, target_w = frame_size

    for frame in frames_bgr:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_AREA)
        processed.append(resized.astype(np.float32) / 255.0)

    return np.asarray(processed, dtype=np.float32)


def _resize_frames_rgb(frames_bgr: np.ndarray, frame_size: Tuple[int, int]) -> np.ndarray:
    """Convert BGR->RGB and resize without normalization for feature extraction."""
    processed = []
    target_h, target_w = frame_size

    for frame in frames_bgr:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (target_w, target_h), interpolation=cv2.INTER_AREA)
        processed.append(resized.astype(np.float32))

    return np.asarray(processed, dtype=np.float32)


@lru_cache(maxsize=1)
def _get_efficientnet_feature_extractor() -> tf.keras.Model:
    """Create a frame-level EfficientNetV2B0 encoder returning 1280-d features."""
    return EfficientNetV2B0(include_top=False, pooling="avg", weights="imagenet")


def _build_feature_sequence_from_video(
    video_path: str,
    time_steps: int,
    feature_dim: int,
    frame_size: Tuple[int, int] = (FRAME_HEIGHT, FRAME_WIDTH),
) -> np.ndarray:
    """Build a single feature-sequence tensor with shape (1, T, F)."""
    raw_frames = _read_frames_uniform(video_path, time_steps)
    frames_rgb = _resize_frames_rgb(raw_frames, frame_size)
    frames_preprocessed = preprocess_input(frames_rgb)

    extractor = _get_efficientnet_feature_extractor()
    frame_features = extractor.predict(frames_preprocessed, verbose=0)

    if frame_features.ndim != 2:
        raise ValueError(
            f"Unexpected extracted feature shape: {frame_features.shape}, expected (T, F)"
        )

    extracted_dim = int(frame_features.shape[1])
    if extracted_dim < feature_dim:
        # Some models may have been trained with concatenated handcrafted features.
        # We keep inference running by zero-padding the missing dimensions.
        pad_width = feature_dim - extracted_dim
        frame_features = np.pad(frame_features, ((0, 0), (0, pad_width)), mode="constant")
    elif extracted_dim > feature_dim:
        frame_features = frame_features[:, :feature_dim]

    return np.expand_dims(frame_features.astype(np.float32), axis=0)


def build_sequence_from_video(
    video_path: str,
    time_steps: int = TIME_STEPS,
    frame_size: Tuple[int, int] = (FRAME_HEIGHT, FRAME_WIDTH),
) -> np.ndarray:
    """Build a single video sequence tensor with shape (1, T, H, W, C)."""
    raw_frames = _read_frames_uniform(video_path, time_steps)
    sequence = _preprocess_frames(raw_frames, frame_size)

    if sequence.shape != (time_steps, frame_size[0], frame_size[1], CHANNELS):
        raise ValueError(
            "Unexpected sequence shape: "
            f"{sequence.shape}, expected ({time_steps}, {frame_size[0]}, {frame_size[1]}, {CHANNELS})"
        )

    return np.expand_dims(sequence, axis=0)


def prepare_input_for_model(model: tf.keras.Model, video_path: str) -> np.ndarray:
    """Build and validate input tensor against model input shape."""
    model_input_shape = model.input_shape
    if not isinstance(model_input_shape, tuple):
        raise ValueError(f"Unsupported input shape container: {model_input_shape}")

    if len(model_input_shape) == 5:
        _, t, h, w, c = model_input_shape
        t = TIME_STEPS if t is None else int(t)
        h = FRAME_HEIGHT if h is None else int(h)
        w = FRAME_WIDTH if w is None else int(w)
        c = CHANNELS if c is None else int(c)

        if (t, h, w, c) != (TIME_STEPS, FRAME_HEIGHT, FRAME_WIDTH, CHANNELS):
            raise ValueError(
                "Model input shape mismatch. "
                f"Expected (None, {TIME_STEPS}, {FRAME_HEIGHT}, {FRAME_WIDTH}, {CHANNELS}), "
                f"got {model_input_shape}"
            )

        return build_sequence_from_video(video_path, time_steps=t, frame_size=(h, w))

    if len(model_input_shape) == 3:
        _, t, f = model_input_shape
        t = 16 if t is None else int(t)
        f = 1280 if f is None else int(f)
        return _build_feature_sequence_from_video(video_path, time_steps=t, feature_dim=f)

    raise ValueError(
        f"Expected 5D frame input or 3D feature-sequence input model, got input_shape={model_input_shape}"
    )


def extract_shoplifting_probability(predictions: np.ndarray) -> float:
    """Normalize model outputs into a single shoplifting probability in [0, 1]."""
    pred = np.asarray(predictions)

    if pred.ndim == 0:
        return float(np.clip(pred.item(), 0.0, 1.0))

    if pred.ndim == 1:
        if pred.shape[0] == 1:
            return float(np.clip(pred[0], 0.0, 1.0))
        # Assume two-class output [normal, shoplifting] when length is 2.
        if pred.shape[0] == 2:
            return float(np.clip(pred[1], 0.0, 1.0))

    if pred.ndim >= 2:
        row = pred[0]
        if np.ndim(row) == 0:
            return float(np.clip(row.item(), 0.0, 1.0))
        if len(row) == 1:
            return float(np.clip(row[0], 0.0, 1.0))
        if len(row) >= 2:
            return float(np.clip(row[1], 0.0, 1.0))

    raise ValueError(f"Unsupported prediction shape: {pred.shape}")


def predict_video_probability(model: tf.keras.Model, video_path: str) -> float:
    """End-to-end helper: preprocess video and return shoplifting probability."""
    model_input = prepare_input_for_model(model, video_path)
    predictions = model.predict(model_input, verbose=0)
    return extract_shoplifting_probability(predictions)
