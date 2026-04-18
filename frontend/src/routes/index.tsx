import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState, useCallback } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Tooltip,
  Filler,
} from "chart.js";
import { Bar, Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  Tooltip,
  Filler,
);

export const Route = createFileRoute("/")({
  component: SmartSurveil,
  head: () => ({
    meta: [
      { title: "Smart Surveil — Real-time Shoplifting Detection" },
      {
        name: "description",
        content:
          "Smart Surveil dashboard for stores to monitor real-time shoplifting detection across uploaded video and live RTSP cameras.",
      },
    ],
    links: [
      { rel: "preconnect", href: "https://fonts.googleapis.com" },
      {
        rel: "preconnect",
        href: "https://fonts.gstatic.com",
        crossOrigin: "anonymous",
      },
      {
        rel: "stylesheet",
        href: "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
      },
    ],
  }),
});

// ── Types matching backend contract from index.html ──
type DotState = "idle" | "ok" | "warn" | "err";
type VideoStatus = "pending" | "processing" | "done" | "failed";
type VideoRow = {
  id: number;
  filename: string;
  status: VideoStatus;
  incidents: number;
  model: string;
};
type Stats = {
  today_total: number;
  this_hour: number;
  total_all_time: number;
  high_risk_hours: number[];
  hourly_today: { hour: number; count: number }[];
  daily_last_7: { date: string; count: number }[];
};
type AlertMsg = {
  id: string;
  ts: number;
  probability: number;
  source?: string;
  video_id?: number;
  track_id?: number;
  model?: string;
  frame_index?: number | null;
  snapshot?: string;
};

const MODELS = [
  { id: "B", label: "Model B — D1 Dataset (recommended)" },
  { id: "A", label: "Model A — D1+Lab, Attention LSTM" },
  { id: "C", label: "Model C — Lab Dataset" },
];

function playAlertSound() {
  try {
    const Ctx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext: typeof AudioContext })
        .webkitAudioContext;
    const ctx = new Ctx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = "sawtooth";
    osc.frequency.setValueAtTime(440, ctx.currentTime);
    osc.frequency.setValueAtTime(660, ctx.currentTime + 0.1);
    osc.frequency.setValueAtTime(440, ctx.currentTime + 0.2);
    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.55);
  } catch {
    /* ignore */
  }
}

function SmartSurveil() {
  // ── connection / source state ──
  const [tab, setTab] = useState<"upload" | "rtsp">("upload");
  const [ngrokUrl, setNgrokUrl] = useState("");
  const [wsState, setWsState] = useState<DotState>("idle");
  const [kgState, setKgState] = useState<DotState>("idle");
  const [dbState, setDbState] = useState<DotState>("idle");

  const [model, setModel] = useState("B");
  const [rtspModel, setRtspModel] = useState("B");
  const [rtspUrl, setRtspUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [uploadStatus, setUploadStatus] = useState("");
  const [rtspStatus, setRtspStatus] = useState("");

  // ── feed state ──
  const [feedFrame, setFeedFrame] = useState<string | null>(null);
  const [feedSource, setFeedSource] = useState("— no source —");
  const [progress, setProgress] = useState(0);
  const [alerting, setAlerting] = useState(false);
  const [activeVideoId, setActiveVideoId] = useState<number | null>(null);
  const [showReplay, setShowReplay] = useState(false);

  // ── data ──
  const [videos, setVideos] = useState<VideoRow[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [alerts, setAlerts] = useState<AlertMsg[]>([]);

  // ── refs ──
  const alertWsRef = useRef<WebSocket | null>(null);
  const streamWsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const pingTimerRef = useRef<number | null>(null);

  // ── helpers ──
  const flashFeed = useCallback(() => {
    setAlerting(false);
    requestAnimationFrame(() => setAlerting(true));
    window.setTimeout(() => setAlerting(false), 1600);
  }, []);

  const pushAlert = useCallback((msg: Omit<AlertMsg, "id" | "ts">) => {
    setAlerts((prev) =>
      [{ ...msg, id: crypto.randomUUID(), ts: Date.now() }, ...prev].slice(
        0,
        20,
      ),
    );
  }, []);

  // ── API calls (relative paths exactly like index.html) ──
  const loadStats = useCallback(async () => {
    try {
      const r = await fetch("/api/stats");
      if (!r.ok) return;
      const d: Stats = await r.json();
      setStats(d);
    } catch {
      /* offline */
    }
  }, []);

  const loadVideos = useCallback(async () => {
    try {
      const r = await fetch("/api/videos");
      if (!r.ok) return;
      const d: VideoRow[] = await r.json();
      setVideos(d);
    } catch {
      /* offline */
    }
  }, []);

  const checkHealth = useCallback(async () => {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      const ok =
        typeof d.kaggle === "object" && d.kaggle?.status === "ok";
      setKgState(ok ? "ok" : "warn");
      setDbState("ok");
    } catch {
      setKgState("err");
      setDbState("err");
    }
  }, []);

  const setKaggleUrl = useCallback(async () => {
    if (!ngrokUrl.trim()) return;
    const fd = new FormData();
    fd.append("url", ngrokUrl.trim());
    try {
      await fetch("/api/kaggle-url", { method: "POST", body: fd });
    } catch {
      /* ignore */
    }
    checkHealth();
  }, [ngrokUrl, checkHealth]);

  // ── Inference WebSocket per video ──
  const startInferStream = useCallback(
    (videoId: number) => {
      if (streamWsRef.current) {
        streamWsRef.current.close();
        streamWsRef.current = null;
      }
      setActiveVideoId(videoId);
      setFeedSource(`Video #${videoId} — Live Inference`);
      setShowReplay(false);
      setProgress(0);
      setFeedFrame(null);

      const ws = new WebSocket(
        `ws://${window.location.host}/ws/infer/${videoId}`,
      );
      streamWsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "frame") {
            setFeedFrame(msg.frame);
            if (msg.total && msg.frame_idx) {
              setProgress((msg.frame_idx / msg.total) * 100);
            }
          } else if (msg.type === "meta") {
            setFeedSource(
              `Video #${videoId} · ${msg.model} · ${msg.total} frames · ${Math.round(msg.fps)}fps`,
            );
          } else if (msg.type === "done") {
            setProgress(100);
            setShowReplay(true);
            setFeedSource((s) => s + " — Done");
            loadStats();
            loadVideos();
          } else if (msg.type === "ERROR") {
            setUploadStatus(`Error: ${msg.message}`);
          }
        } catch {
          /* malformed */
        }
      };
      ws.onerror = () => setUploadStatus("Stream connection error");
    },
    [loadStats, loadVideos],
  );

  // ── Upload ──
  const uploadVideo = useCallback(async () => {
    if (!file) {
      setUploadStatus("Select a video file first");
      return;
    }
    const fd = new FormData();
    fd.append("video", file);
    fd.append("model", model);
    setUploadStatus("Uploading…");
    try {
      const r = await fetch("/api/videos/upload", {
        method: "POST",
        body: fd,
      });
      const d = await r.json();
      setUploadStatus(`Video #${d.video_id} uploaded — connecting stream…`);
      window.setTimeout(() => startInferStream(d.video_id), 500);
    } catch (err) {
      setUploadStatus(`Upload failed: ${(err as Error).message}`);
    }
  }, [file, model, startInferStream]);

  // ── RTSP ──
  const startRtsp = useCallback(async () => {
    if (!rtspUrl.trim()) {
      setRtspStatus("Enter RTSP URL");
      return;
    }
    const fd = new FormData();
    fd.append("url", rtspUrl.trim());
    fd.append("model", rtspModel);
    try {
      const r = await fetch("/api/rtsp/start", {
        method: "POST",
        body: fd,
      });
      const d = await r.json();
      setRtspStatus(d.ok ? `Streaming ${rtspUrl}` : d.message || "Error");
      if (d.ok) {
        setFeedSource("RTSP LIVE");
        setFeedFrame(null);
      }
    } catch (err) {
      setRtspStatus(`Failed: ${(err as Error).message}`);
    }
  }, [rtspUrl, rtspModel]);

  const stopRtsp = useCallback(async () => {
    try {
      await fetch("/api/rtsp/stop", { method: "POST" });
    } catch {
      /* ignore */
    }
    setRtspStatus("Stopped");
    setFeedSource("— no source —");
    setFeedFrame(null);
  }, []);

  const stopStream = useCallback(() => {
    if (streamWsRef.current) {
      streamWsRef.current.close();
      streamWsRef.current = null;
    }
    setFeedFrame(null);
    setFeedSource("— no source —");
    setShowReplay(false);
    setProgress(0);
  }, []);

  const replayVideo = useCallback(() => {
    if (activeVideoId !== null) startInferStream(activeVideoId);
  }, [activeVideoId, startInferStream]);

  const dismissAlert = useCallback((id: string) => {
    setAlerts((a) => a.filter((x) => x.id !== id));
  }, []);

  const clearAlerts = useCallback(() => setAlerts([]), []);

  const selectVideo = useCallback(
    (v: VideoRow) => {
      if (v.status === "done" || v.status === "pending") {
        startInferStream(v.id);
      }
    },
    [startInferStream],
  );

  // ── Alert WebSocket lifecycle ──
  useEffect(() => {
    let cancelled = false;

    function connect() {
      if (cancelled) return;
      const ws = new WebSocket(`ws://${window.location.host}/ws/alerts`);
      alertWsRef.current = ws;

      ws.onopen = () => {
        setWsState("ok");
        if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
        pingTimerRef.current = window.setInterval(() => {
          if (ws.readyState === 1) ws.send("ping");
        }, 20000);
      };

      ws.onclose = () => {
        setWsState("err");
        if (pingTimerRef.current) {
          window.clearInterval(pingTimerRef.current);
          pingTimerRef.current = null;
        }
        reconnectTimerRef.current = window.setTimeout(connect, 3000);
      };

      ws.onerror = () => setWsState("err");

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === "FRAME") {
            setFeedFrame(msg.frame);
          } else if (msg.type === "ALERT") {
            playAlertSound();
            pushAlert(msg);
            flashFeed();
            loadStats();
          } else if (msg.type === "STATUS") {
            setUploadStatus(
              `Video #${msg.video_id}: ${String(msg.status).toUpperCase()}`,
            );
            loadVideos();
            if (msg.status === "done" || msg.status === "processing") {
              loadStats();
            }
          } else if (msg.type === "RTSP_ERROR") {
            setRtspStatus(`Error: ${msg.error}`);
          } else if (msg.type === "RTSP_STOPPED") {
            setRtspStatus("Stream stopped");
          }
        } catch {
          /* ignore non-JSON */
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      if (reconnectTimerRef.current) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (pingTimerRef.current) {
        window.clearInterval(pingTimerRef.current);
      }
      if (alertWsRef.current) alertWsRef.current.close();
      if (streamWsRef.current) streamWsRef.current.close();
    };
  }, [flashFeed, pushAlert, loadStats, loadVideos]);

  // ── Polling like the original ──
  useEffect(() => {
    checkHealth();
    loadStats();
    loadVideos();
    const a = window.setInterval(loadStats, 20000);
    const b = window.setInterval(loadVideos, 10000);
    const c = window.setInterval(checkHealth, 30000);
    return () => {
      window.clearInterval(a);
      window.clearInterval(b);
      window.clearInterval(c);
    };
  }, [checkHealth, loadStats, loadVideos]);

  // ── chart data ──
  const hourlyData = useMemo(() => {
    const labels = stats?.hourly_today.map((x) => `${x.hour}:00`) ?? [];
    const data = stats?.hourly_today.map((x) => x.count) ?? [];
    return {
      labels,
      datasets: [
        {
          data,
          backgroundColor: "rgba(220, 38, 38, 0.65)",
          borderColor: "rgba(220, 38, 38, 1)",
          borderWidth: 1,
          borderRadius: 3,
        },
      ],
    };
  }, [stats]);

  const dailyData = useMemo(() => {
    const labels = stats?.daily_last_7.map((x) => x.date.slice(5)) ?? [];
    const data = stats?.daily_last_7.map((x) => x.count) ?? [];
    return {
      labels,
      datasets: [
        {
          data,
          borderColor: "rgb(79, 70, 229)",
          backgroundColor: "rgba(79, 70, 229, 0.12)",
          tension: 0.35,
          fill: true,
          pointBackgroundColor: "rgb(79, 70, 229)",
          pointRadius: 3,
          borderWidth: 2,
        },
      ],
    };
  }, [stats]);

  const chartOpts = useMemo(
    () =>
      ({
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { enabled: true } },
        scales: {
          x: {
            ticks: { color: "#64748b", font: { size: 10 } },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#64748b", font: { size: 10 }, stepSize: 1 },
            grid: { color: "rgba(0,0,0,0.05)" },
            beginAtZero: true,
          },
        },
      }) as const,
    [],
  );

  // ── derived ──
  const highRisk = stats?.high_risk_hours?.length
    ? stats.high_risk_hours.map((h) => `${h}:00`).join(" · ")
    : "none detected";

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {/* Header */}
      <header className="flex h-14 flex-shrink-0 items-center gap-4 border-b border-border bg-surface px-5">
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <ShieldIcon />
          </div>
          <div className="text-[1.05rem] font-semibold tracking-tight">
            Smart Surveil
          </div>
          <span className="ml-1 hidden rounded bg-muted px-1.5 py-0.5 text-[0.65rem] font-medium text-muted-foreground sm:inline">
            v1.0
          </span>
        </div>

        <div className="ml-2 flex gap-1.5">
          <StatusPill label="WS" state={wsState} />
          <StatusPill label="Inference" state={kgState} />
          <StatusPill label="DB" state={dbState} />
        </div>

        <div className="ml-auto flex items-center gap-2">
          <input
            value={ngrokUrl}
            onChange={(e) => setNgrokUrl(e.target.value)}
            placeholder="https://xxxx.ngrok-free.app"
            className="hidden w-[300px] rounded-md border border-border bg-background px-3 py-1.5 text-[0.78rem] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring md:block"
          />
          <button
            onClick={setKaggleUrl}
            className="rounded-md bg-primary px-3.5 py-1.5 text-[0.78rem] font-medium text-primary-foreground transition hover:opacity-90"
          >
            Connect
          </button>
        </div>
      </header>

      {/* Layout */}
      <div className="grid h-[calc(100vh-3.5rem)] grid-cols-[280px_1fr_320px] overflow-hidden">
        {/* Sidebar */}
        <aside className="flex flex-col overflow-y-auto border-r border-border bg-surface">
          <Section title="Video Source">
            <div className="mb-3 inline-flex w-full rounded-md bg-muted p-0.5">
              <TabBtn active={tab === "upload"} onClick={() => setTab("upload")}>
                Upload
              </TabBtn>
              <TabBtn active={tab === "rtsp"} onClick={() => setTab("rtsp")}>
                RTSP
              </TabBtn>
            </div>

            {tab === "upload" ? (
              <div className="space-y-2.5">
                <Field label="Video file">
                  <input
                    type="file"
                    accept="video/*"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="block w-full text-[0.75rem] text-foreground file:mr-2 file:rounded-md file:border-0 file:bg-muted file:px-2.5 file:py-1.5 file:text-[0.72rem] file:font-medium file:text-foreground hover:file:bg-accent"
                  />
                </Field>
                <Field label="Model">
                  <Select value={model} onChange={setModel}>
                    {MODELS.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <button
                  onClick={uploadVideo}
                  className="mt-1 flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-[0.8rem] font-medium text-primary-foreground transition hover:opacity-90"
                >
                  ▶ Run Inference
                </button>
                {uploadStatus && (
                  <div className="text-[0.72rem] text-muted-foreground">
                    {uploadStatus}
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                <Field label="RTSP URL">
                  <Input
                    value={rtspUrl}
                    onChange={setRtspUrl}
                    placeholder="rtsp://192.168.1.x:554/stream"
                  />
                </Field>
                <Field label="Model">
                  <Select value={rtspModel} onChange={setRtspModel}>
                    {MODELS.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.id} — {m.label.split("—")[1]?.trim() ?? m.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <div className="flex gap-1.5">
                  <button
                    onClick={startRtsp}
                    className="flex-1 rounded-md bg-success px-3 py-1.5 text-[0.78rem] font-medium text-white transition hover:opacity-90"
                    style={{ background: "var(--success)" }}
                  >
                    ▶ Start
                  </button>
                  <button
                    onClick={stopRtsp}
                    className="flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-[0.78rem] font-medium text-foreground transition hover:bg-muted"
                  >
                    ■ Stop
                  </button>
                </div>
                {rtspStatus && (
                  <div className="text-[0.72rem] text-muted-foreground">
                    {rtspStatus}
                  </div>
                )}
              </div>
            )}
          </Section>

          <Section title="Statistics">
            <div className="grid grid-cols-2 gap-2">
              <StatBox n={stats?.today_total ?? "—"} label="Today" />
              <StatBox n={stats?.this_hour ?? "—"} label="This hour" />
              <StatBox n={stats?.total_all_time ?? "—"} label="All time" />
              <StatBox n={videos.length || "—"} label="Videos" />
              <div className="col-span-2 rounded-md border border-border bg-background p-2.5">
                <div className="text-[0.62rem] font-medium uppercase tracking-wide text-muted-foreground">
                  High risk hours
                </div>
                <div
                  className={`mt-0.5 text-[0.78rem] font-medium ${stats?.high_risk_hours?.length ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {highRisk}
                </div>
              </div>
            </div>
          </Section>

          <Section title="Hourly activity (today)">
            <div className="h-[100px]">
              <Bar data={hourlyData} options={chartOpts} />
            </div>
          </Section>

          <Section title="Processed videos">
            {videos.length === 0 ? (
              <div className="text-[0.72rem] text-muted-foreground">
                No videos yet
              </div>
            ) : (
              <div className="-mx-1">
                {videos.slice(0, 12).map((v) => (
                  <button
                    key={v.id}
                    onClick={() => selectVideo(v)}
                    className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-2 text-left transition hover:bg-muted"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[0.75rem] font-medium text-foreground">
                        {v.filename}
                      </div>
                      <div className="text-[0.65rem] text-muted-foreground">
                        {v.incidents} incident{v.incidents === 1 ? "" : "s"} ·{" "}
                        {v.model}
                      </div>
                    </div>
                    <VideoStatusBadge status={v.status} />
                  </button>
                ))}
              </div>
            )}
          </Section>
        </aside>

        {/* Centre — feed */}
        <section className="flex flex-col overflow-hidden bg-background">
          <div className="flex flex-shrink-0 items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
            <div className="text-[0.78rem] font-semibold uppercase tracking-wide text-muted-foreground">
              Live feed
            </div>
            <div className="truncate text-[0.78rem] font-medium text-foreground">
              {feedSource}
            </div>
            <div className="ml-auto flex gap-1.5">
              {showReplay && (
                <button
                  onClick={replayVideo}
                  className="rounded-md border border-border bg-background px-2.5 py-1 text-[0.72rem] font-medium text-foreground transition hover:bg-muted"
                >
                  ↺ Replay
                </button>
              )}
              <button
                onClick={stopStream}
                className="rounded-md border border-border bg-background px-2.5 py-1 text-[0.72rem] font-medium text-foreground transition hover:bg-muted"
              >
                ■ Stop
              </button>
            </div>
          </div>

          <div className="h-1 flex-shrink-0 bg-muted">
            <div
              className="h-full bg-primary transition-[width] duration-200 ease-linear"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div
            className={`relative flex flex-1 items-center justify-center overflow-hidden bg-slate-900 ${alerting ? "alerting" : ""}`}
          >
            {feedFrame ? (
              <img
                src={`data:image/jpeg;base64,${feedFrame}`}
                alt="live inference frame"
                className="max-h-full max-w-full object-contain"
              />
            ) : (
              <div className="flex flex-col items-center gap-3 text-center text-slate-400">
                <CameraIcon />
                <div className="text-[0.85rem] font-medium">No feed active</div>
                <div className="text-[0.72rem] text-slate-500">
                  Upload a video or connect an RTSP stream to begin
                </div>
              </div>
            )}
          </div>

          <div className="flex-shrink-0 border-t border-border bg-surface px-4 py-3">
            <div className="mb-2 text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground">
              Daily incidents (last 7 days)
            </div>
            <div className="h-[110px]">
              <Line data={dailyData} options={chartOpts} />
            </div>
          </div>
        </section>

        {/* Right — alerts */}
        <aside className="flex flex-col overflow-hidden border-l border-border bg-surface">
          <div className="flex flex-shrink-0 items-center gap-2 border-b border-border px-4 py-3">
            <div className="text-[0.95rem] font-semibold">Alerts</div>
            <span className="rounded-full bg-destructive px-2 py-0.5 text-[0.68rem] font-semibold text-destructive-foreground">
              {alerts.length}
            </span>
            <button
              onClick={clearAlerts}
              className="ml-auto rounded-md border border-border bg-background px-2 py-0.5 text-[0.7rem] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground"
            >
              Clear
            </button>
          </div>

          <div className="flex flex-1 flex-col gap-2 overflow-y-auto p-3">
            {alerts.length === 0 ? (
              <div className="py-10 text-center text-[0.78rem] text-muted-foreground">
                No incidents detected
              </div>
            ) : (
              alerts.map((a, i) => (
                <AlertCard
                  key={a.id}
                  alert={a}
                  onDismiss={dismissAlert}
                  isLatest={i === 0}
                />
              ))
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

// ── Sub-components ──

function StatusPill({ label, state }: { label: string; state: DotState }) {
  const cfg = {
    idle: { dot: "bg-slate-300", text: "text-muted-foreground", pulse: "" },
    ok: { dot: "bg-success", text: "text-foreground", pulse: "dot-pulse" },
    warn: { dot: "bg-warning", text: "text-foreground", pulse: "" },
    err: { dot: "bg-destructive", text: "text-foreground", pulse: "" },
  }[state];
  return (
    <div className="inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-[0.68rem] font-medium">
      <span
        className={`h-1.5 w-1.5 rounded-full ${cfg.dot} ${cfg.pulse}`}
        style={{
          background:
            state === "ok"
              ? "var(--success)"
              : state === "warn"
                ? "var(--warning)"
                : state === "err"
                  ? "var(--destructive)"
                  : undefined,
        }}
      />
      <span className={cfg.text}>{label}</span>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-b border-border px-4 py-3.5">
      <div className="mb-2.5 text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  );
}

function TabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 rounded px-3 py-1 text-[0.78rem] font-medium transition ${
        active
          ? "bg-surface text-foreground shadow-sm"
          : "text-muted-foreground hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1 block text-[0.68rem] font-medium text-muted-foreground">
        {label}
      </label>
      {children}
    </div>
  );
}

function Input({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <input
      type="text"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-[0.75rem] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
    />
  );
}

function Select({
  value,
  onChange,
  children,
}: {
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-[0.75rem] text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring"
    >
      {children}
    </select>
  );
}

function StatBox({ n, label }: { n: number | string; label: string }) {
  return (
    <div className="rounded-md border border-border bg-background p-2.5">
      <div className="text-[1.4rem] font-semibold leading-none text-foreground">
        {n}
      </div>
      <div className="mt-1 text-[0.62rem] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
    </div>
  );
}

function VideoStatusBadge({ status }: { status: VideoStatus }) {
  const map: Record<VideoStatus, { cls: string; label: string }> = {
    done: {
      cls: "bg-emerald-50 text-emerald-700 ring-emerald-200",
      label: "Done",
    },
    processing: {
      cls: "bg-amber-50 text-amber-700 ring-amber-200",
      label: "Proc",
    },
    failed: { cls: "bg-red-50 text-red-700 ring-red-200", label: "Fail" },
    pending: { cls: "bg-slate-50 text-slate-600 ring-slate-200", label: "Pend" },
  };
  const { cls, label } = map[status];
  return (
    <span
      className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[0.62rem] font-medium ring-1 ring-inset ${cls}`}
    >
      {label}
    </span>
  );
}

function AlertCard({
  alert,
  onDismiss,
  isLatest,
}: {
  alert: AlertMsg;
  onDismiss: (id: string) => void;
  isLatest: boolean;
}) {
  const time = new Date(alert.ts).toLocaleTimeString();
  const src =
    alert.source === "rtsp" ? "RTSP Live" : `Video #${alert.video_id ?? "?"}`;
  return (
    <div
      className={`slide-in relative rounded-lg border p-3 ${
        isLatest
          ? "border-destructive bg-red-50/60 shadow-sm"
          : "border-border bg-background"
      }`}
    >
      <button
        onClick={() => onDismiss(alert.id)}
        className="absolute right-2 top-2 text-muted-foreground transition hover:text-foreground"
        aria-label="Dismiss"
      >
        ✕
      </button>
      <div className="text-[0.65rem] font-medium text-muted-foreground">
        {time} · {src}
      </div>
      <div className="mt-1 text-[1.5rem] font-semibold leading-none text-destructive">
        {(alert.probability * 100).toFixed(1)}%
      </div>
      <div className="mt-1 text-[0.68rem] text-muted-foreground">
        Track #{alert.track_id ?? "—"} · Model {alert.model ?? "—"} · Frame{" "}
        {alert.frame_index ?? "—"}
      </div>
      {alert.snapshot && (
        <img
          src={`data:image/jpeg;base64,${alert.snapshot}`}
          alt="snapshot"
          className="mt-2 w-full rounded-md border border-border"
        />
      )}
    </div>
  );
}

function ShieldIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="m9 12 2 2 4-4" />
    </svg>
  );
}

function CameraIcon() {
  return (
    <svg
      width="44"
      height="44"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="opacity-50"
    >
      <path d="M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" />
      <circle cx="12" cy="13" r="4" />
    </svg>
  );
}
