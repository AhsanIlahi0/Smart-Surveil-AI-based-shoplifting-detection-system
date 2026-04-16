import { useState, useRef } from "react";
import axios from "axios";
import { getApiBase } from "../App.jsx";

const ACCEPTED = ".mp4,.avi,.mov,.mkv";

export default function VideoUpload({
  selectedModel,
  setIsLoading,
  isLoading,
  onResult,
  onCompareResults,
}) {
  const [file, setFile] = useState(null);
  const [videoUrl, setVideoUrl] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const handleFile = (f) => {
    setError(null);
    setFile(f);
    setVideoUrl(URL.createObjectURL(f));
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  };

  const runInference = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("video", file);
      form.append("model", selectedModel);
      // Run Inference
      const res = await axios.post(`${getApiBase()}/predict`, form, {
        headers: {
          "Content-Type": "multipart/form-data",
          "ngrok-skip-browser-warning": "true",
        },
        timeout: 120000,
      });

      onResult(res.data, file.name);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Request failed");
    } finally {
      setIsLoading(false);
    }
  };

  const runCompare = async () => {
    if (!file) return;
    setIsLoading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("video", file);

      // Compare
      const res = await axios.post(`${getApiBase()}/predict/compare`, form, {
        headers: {
          "Content-Type": "multipart/form-data",
          "ngrok-skip-browser-warning": "true",
        },
        timeout: 300000,
      });

      onCompareResults(res.data, file.name);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || "Request failed");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
          ${dragOver ? "border-accent bg-accent/10" : "border-border hover:border-accent/60 hover:bg-white/5"}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={(e) => e.target.files[0] && handleFile(e.target.files[0])}
        />
        <div className="text-4xl mb-3">🎬</div>
        {file ? (
          <p className="text-white font-semibold">{file.name}</p>
        ) : (
          <>
            <p className="text-white font-semibold">Drag & drop a video here</p>
            <p className="text-muted text-sm mt-1">
              or click to browse — MP4, AVI, MOV, MKV
            </p>
          </>
        )}
      </div>

      {/* Video preview */}
      {videoUrl && (
        <video
          src={videoUrl}
          controls
          className="w-full max-h-72 rounded-xl border border-border object-contain bg-black"
        />
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/40 border border-red-500/50 rounded-lg px-4 py-3 text-red-300 text-sm">
          ⚠️ {error}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={runInference}
          disabled={!file || isLoading}
          className="flex-1 min-w-[160px] px-6 py-3 bg-accent text-black font-bold rounded-xl hover:bg-white transition disabled:opacity-40 disabled:cursor-not-allowed text-sm"
        >
          🔍 Run Inference
        </button>
        <button
          onClick={runCompare}
          disabled={!file || isLoading}
          className="flex-1 min-w-[160px] px-6 py-3 bg-transparent border border-accent text-accent font-bold rounded-xl hover:bg-accent hover:text-black transition disabled:opacity-40 disabled:cursor-not-allowed text-sm"
        >
          ⚖️ Compare All 3 Models
        </button>
      </div>
    </div>
  );
}
