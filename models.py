from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

if __package__:
    from .database import Base
else:
    from database import Base


class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String)  # local path: uploads/
    # pending|processing|done|failed|stopped
    status = Column(String, default="pending")
    source_type = Column(String, default="upload")  # upload|rtsp
    source_url = Column(String)  # rtsp URL if applicable
    model_used = Column(String, default="B")  # A, B, or C
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow,
                        onupdate=datetime.utcnow)
    annotated_filepath = Column(String)
    results = relationship(
        "InferenceResult", back_populates="video", cascade="all, delete"
    )
    incidents = relationship(
        "Incident", back_populates="video", cascade="all, delete")


class InferenceResult(Base):
    __tablename__ = "inference_results"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"))
    model = Column(String)
    threshold = Column(Float)
    total_frames = Column(Integer)
    unique_tracks = Column(Integer)
    shoplifting_tracks = Column(Integer)
    inference_seconds = Column(Float)
    majority_vote = Column(String)  # populated for /compare runs
    created_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="results")
    incidents = relationship("Incident", back_populates="result")


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"))
    result_id = Column(Integer, ForeignKey(
        "inference_results.id", ondelete="CASCADE"))
    track_id = Column(Integer)
    frame_index = Column(Integer)
    probability = Column(Float)
    model = Column(String)
    snapshot_b64 = Column(Text)  # base64 JPEG snapshot from Kaggle
    detected_at = Column(DateTime, default=datetime.utcnow)

    video = relationship("Video", back_populates="incidents")
    result = relationship("InferenceResult", back_populates="incidents")
