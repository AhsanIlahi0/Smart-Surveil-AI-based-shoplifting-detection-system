import { useRef, useState, useEffect } from "react";
import axios from "axios";
import { getApiBase } from "../App.jsx";

export default function WebcamCapture({
  selectedModel,
  setIsLoading,
  isLoading,
  onResult,
}) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const [streaming, setStreaming] = useState(false);
  const [permissionDenied, setPermissionDenied] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    return () => stopStream();
  }, []);

  const startStream = async () => {
    setError(null);
    setPermissionDenied(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment", width: 640, height: 480 },
        audio: false,
      });
      streamRef.current = stream;
      videoRef.current.srcObject = stream;
      await videoRef.current.play();
      setStreaming(true);
    } catch (err) {
      if (err.name === "NotAllowedError") {
        setPermissionDenied(true);
      } else {
        setError("Could not start camera: " + err.message);
      }
    }
  };

  const stopStream = () => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    setStreaming(false);
  };

  const captureFrames = async () => {
    if (!streaming || !videoRef.current) return;
    setIsLoading(true);
    setError(null);

    try {
      const video = videoRef.current;
      const canvas = canvasRef.current;
      const ctx = canvas.getContext("2d");
      canvas.width = 224;
      canvas.height = 224;

      const frames_b64 = [];
      for (let i = 0; i < 16; i++) {
        ctx.drawImage(video, 0, 0, 224, 224);
        const b64 = canvas.toDataURL("image/jpeg", 0.8).split(",")[1];
        frames_b64.push(b64);
        // small delay between captures (~200ms apart)
        await new Promise((r) => setTimeout(r, 200));
      }
      const res = await axios.post(
        `${getApiBase()}/predict/webcam`,
        { frames_b64, model: selectedModel },
        {
          timeout: 120000,
          headers: { "ngrok-skip-browser-warning": "true" },
        },
      );

      onResult(res.data, "webcam");
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Request failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Video preview */}
      <div className="relative bg-black rounded-xl overflow-hidden border border-border aspect-video max-h-72 flex items-center justify-center">
        <video
          ref={videoRef}
          className="w-full h-full object-contain"
          playsInline
          muted
        />
        {!streaming && (
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-muted text-sm">Camera not started</span>
          </div>
        )}
        {streaming && (
          <div className="absolute top-3 right-3 flex items-center gap-1.5 bg-black/60 rounded-full px-3 py-1">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
            <span className="text-white text-xs">LIVE</span>
          </div>
        )}
      </div>

      <canvas ref={canvasRef} className="hidden" />

      {/* Permission denied */}
      {permissionDenied && (
        <div className="bg-yellow-900/40 border border-yellow-500/50 rounded-lg px-4 py-3 text-yellow-300 text-sm">
          📵 Camera permission denied. Please allow camera access in your
          browser settings and try again.
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/40 border border-red-500/50 rounded-lg px-4 py-3 text-red-300 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Buttons */}
      <div className="flex flex-wrap gap-3">
        {!streaming ? (
          <button
            onClick={startStream}
            className="flex-1 min-w-[160px] px-6 py-3 bg-accent text-black font-bold rounded-xl hover:bg-white transition text-sm"
          >
            📷 Start Camera
          </button>
        ) : (
          <>
            <button
              onClick={captureFrames}
              disabled={isLoading}
              className="flex-1 min-w-[160px] px-6 py-3 bg-accent text-black font-bold rounded-xl hover:bg-white transition disabled:opacity-40 disabled:cursor-not-allowed text-sm"
            >
              📸 Capture &amp; Predict
            </button>
            <button
              onClick={stopStream}
              className="px-6 py-3 bg-transparent border border-red-500 text-red-400 font-bold rounded-xl hover:bg-red-900/30 transition text-sm"
            >
              ⏹ Stop
            </button>
          </>
        )}
      </div>

      <p className="text-muted text-xs">
        Captures 16 frames over ~3 seconds from your live stream, then sends to
        the LSTM model. Works on desktop Chrome and mobile Safari.
      </p>
    </div>
  );
}
