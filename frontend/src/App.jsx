import { useState, useCallback } from "react";
import Header from "./components/Header.jsx";
import ModelSelector from "./components/ModelSelector.jsx";
import VideoUpload from "./components/VideoUpload.jsx";
import WebcamCapture from "./components/WebcamCapture.jsx";
import ResultCard from "./components/ResultCard.jsx";
import FrameGrid from "./components/FrameGrid.jsx";
import ProbabilityGraph from "./components/ProbabilityGraph.jsx";
import CompareView from "./components/CompareView.jsx";
import HistoryLog from "./components/HistoryLog.jsx";

export const API_BASE_KEY = "shoplifting_api_url";
export function getApiBase() {
  return (
    localStorage.getItem(API_BASE_KEY) ||
    import.meta.env.VITE_API_URL ||
    "http://localhost:8000"
  );
}

export function apiHeaders() {
  return {
    "ngrok-skip-browser-warning": "true",
  };
}

export default function App() {
  const [selectedModel, setSelectedModel] = useState("A");
  const [activeTab, setActiveTab] = useState("upload"); // "upload" | "webcam"
  const [result, setResult] = useState(null); // single predict result
  const [compareResults, setCompareResults] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [history, setHistory] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("shoplifting_history") || "[]");
    } catch {
      return [];
    }
  });

  const addToHistory = useCallback((entry) => {
    setHistory((prev) => {
      const updated = [entry, ...prev].slice(0, 5);
      localStorage.setItem("shoplifting_history", JSON.stringify(updated));
      return updated;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    localStorage.removeItem("shoplifting_history");
  }, []);

  const handleResult = useCallback(
    (res, filename) => {
      setResult(res);
      setCompareResults(null);
      addToHistory({
        timestamp: new Date().toISOString(),
        model: res.model,
        filename: filename || "webcam",
        label: res.label,
        confidence: res.probability,
      });
    },
    [addToHistory],
  );

  const handleCompareResults = useCallback(
    (res, filename) => {
      setCompareResults(res);
      setResult(null);
      res.results.forEach((r) => {
        addToHistory({
          timestamp: new Date().toISOString(),
          model: r.model,
          filename: filename || "unknown",
          label: r.label,
          confidence: r.probability,
        });
      });
    },
    [addToHistory],
  );

  return (
    <div className="min-h-screen bg-app text-white font-mono">
      <Header />

      {/* Sticky Model Selector */}
      <div className="sticky top-0 z-40 bg-surface/95 backdrop-blur-sm border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <ModelSelector selected={selectedModel} onChange={setSelectedModel} />
        </div>
      </div>

      <main className="max-w-7xl mx-auto px-4 py-8 space-y-8">
        {/* Input Tabs */}
        <section>
          <div className="flex gap-1 mb-4 bg-surface border border-border rounded-lg p-1 w-fit">
            {[
              { id: "upload", label: "📁 Video Upload" },
              { id: "webcam", label: "📷 Webcam" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-5 py-2 rounded-md text-sm font-semibold transition-all duration-200 ${
                  activeTab === tab.id
                    ? "bg-accent text-black"
                    : "text-muted hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {activeTab === "upload" && (
            <VideoUpload
              selectedModel={selectedModel}
              setIsLoading={setIsLoading}
              isLoading={isLoading}
              onResult={handleResult}
              onCompareResults={handleCompareResults}
            />
          )}
          {activeTab === "webcam" && (
            <WebcamCapture
              selectedModel={selectedModel}
              setIsLoading={setIsLoading}
              isLoading={isLoading}
              onResult={handleResult}
            />
          )}
        </section>

        {/* Single Model Result */}
        {result && !compareResults && (
          <section className="space-y-6 animate-fadeIn">
            <ResultCard result={result} />
            {result.sampled_frames && result.sampled_frames.length > 0 && (
              <FrameGrid frames={result.sampled_frames} label={result.label} />
            )}
            <ProbabilityGraph
              probs={result.frame_probabilities}
              threshold={result.threshold}
              label={result.label}
              estimated={result.frame_prob_estimated}
            />
          </section>
        )}

        {/* Compare Results */}
        {compareResults && (
          <section className="animate-fadeIn">
            <CompareView data={compareResults} />
          </section>
        )}

        {/* History */}
        <section>
          <HistoryLog history={history} onClear={clearHistory} />
        </section>
      </main>

      {/* Global loading overlay */}
      {isLoading && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center backdrop-blur-sm">
          <div className="bg-surface border border-accent/40 rounded-2xl p-8 text-center space-y-4">
            <div className="w-16 h-16 border-4 border-accent border-t-transparent rounded-full animate-spin mx-auto" />
            <p className="text-accent text-lg font-semibold tracking-widest">
              ANALYZING…
            </p>
            <p className="text-muted text-sm">
              Running YOLO → MobileNetV2 → LSTM
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
