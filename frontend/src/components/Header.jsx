import { useState, useEffect } from "react";
import axios from "axios";
import { API_BASE_KEY, getApiBase } from "../App.jsx";

export default function Header() {
  const [connected, setConnected] = useState(null); // null=checking, true, false
  const [apiUrl, setApiUrl] = useState(getApiBase());
  const [inputUrl, setInputUrl] = useState(getApiBase());
  const [showInput, setShowInput] = useState(false);

  const checkHealth = async (url) => {
    try {
      const res = await axios.get(`${url}/health`, {
        timeout: 5000,
        headers: { "ngrok-skip-browser-warning": "true" },
      });
      setConnected(res.data?.status === "ok");
    } catch {
      setConnected(false);
    }
  };

  useEffect(() => {
    checkHealth(apiUrl);
    const interval = setInterval(() => checkHealth(apiUrl), 15000);
    return () => clearInterval(interval);
  }, [apiUrl]);

  const saveUrl = () => {
    const trimmed = inputUrl.replace(/\/$/, "");
    localStorage.setItem(API_BASE_KEY, trimmed);
    setApiUrl(trimmed);
    setShowInput(false);
    setConnected(null);
    checkHealth(trimmed);
  };

  return (
    <header className="bg-surface border-b border-border">
      <div className="max-w-7xl mx-auto px-4 py-5 flex flex-col md:flex-row md:items-start md:justify-between gap-4">
        {/* Title block */}
        <div>
          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight text-white">
            Shoplifting Detection System 🎥
          </h1>
          <p className="text-muted text-xs md:text-sm mt-1 leading-relaxed max-w-xl">
            YOLO11n → MobileNetV2 + Optical Flow → Attention-LSTM &nbsp;|&nbsp;
            FYP Demo
          </p>
        </div>

        {/* Status + URL input */}
        <div className="flex flex-col items-start md:items-end gap-2 shrink-0">
          {/* Status indicator */}
          <div className="flex items-center gap-2">
            {connected === null && (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-yellow-400 animate-pulse" />
                <span className="text-yellow-400 text-xs font-semibold">
                  Checking…
                </span>
              </>
            )}
            {connected === true && (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-green-400 animate-pulse" />
                <span className="text-green-400 text-xs font-semibold">
                  Backend Connected
                </span>
              </>
            )}
            {connected === false && (
              <>
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <span className="text-red-400 text-xs font-semibold">
                  Backend Offline
                </span>
              </>
            )}
          </div>

          {/* Update API URL */}
          <button
            onClick={() => setShowInput(!showInput)}
            className="text-xs text-accent underline underline-offset-2 hover:text-white transition"
          >
            {showInput ? "Cancel" : "Update API URL"}
          </button>

          {showInput && (
            <div className="flex gap-2 w-full md:w-auto">
              <input
                type="text"
                value={inputUrl}
                onChange={(e) => setInputUrl(e.target.value)}
                placeholder="https://xxxx.loca.lt"
                className="bg-black border border-border rounded-lg px-3 py-1.5 text-xs text-white w-64 focus:outline-none focus:border-accent"
              />
              <button
                onClick={saveUrl}
                className="px-3 py-1.5 bg-accent text-black text-xs font-bold rounded-lg hover:bg-white transition"
              >
                Save
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
