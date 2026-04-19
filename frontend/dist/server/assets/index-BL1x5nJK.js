import { r as reactExports, T as jsxRuntimeExports } from "./worker-entry-B7I7Vn0F.js";
import { C as Chart$1, L as LineController, B as BarController } from "./router-D6bcKHIQ.js";
import "node:events";
import "node:async_hooks";
import "node:stream/web";
import "node:stream";
const defaultDatasetIdKey = "label";
function reforwardRef(ref, value) {
  if (typeof ref === "function") {
    ref(value);
  } else if (ref) {
    ref.current = value;
  }
}
function setOptions(chart, nextOptions) {
  const options = chart.options;
  if (options && nextOptions) {
    Object.assign(options, nextOptions);
  }
}
function setLabels(currentData, nextLabels) {
  currentData.labels = nextLabels;
}
function setDatasets(currentData, nextDatasets, datasetIdKey = defaultDatasetIdKey) {
  const addedDatasets = [];
  currentData.datasets = nextDatasets.map((nextDataset) => {
    const currentDataset = currentData.datasets.find((dataset) => dataset[datasetIdKey] === nextDataset[datasetIdKey]);
    if (!currentDataset || !nextDataset.data || addedDatasets.includes(currentDataset)) {
      return {
        ...nextDataset
      };
    }
    addedDatasets.push(currentDataset);
    Object.assign(currentDataset, nextDataset);
    return currentDataset;
  });
}
function cloneData(data, datasetIdKey = defaultDatasetIdKey) {
  const nextData = {
    labels: [],
    datasets: []
  };
  setLabels(nextData, data.labels);
  setDatasets(nextData, data.datasets, datasetIdKey);
  return nextData;
}
function ChartComponent(props, ref) {
  const { height = 150, width = 300, redraw = false, datasetIdKey, type, data, options, plugins = [], fallbackContent, updateMode, ...canvasProps } = props;
  const canvasRef = reactExports.useRef(null);
  const chartRef = reactExports.useRef(null);
  const renderChart = () => {
    if (!canvasRef.current) return;
    chartRef.current = new Chart$1(canvasRef.current, {
      type,
      data: cloneData(data, datasetIdKey),
      options: options && {
        ...options
      },
      plugins
    });
    reforwardRef(ref, chartRef.current);
  };
  const destroyChart = () => {
    reforwardRef(ref, null);
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }
  };
  reactExports.useEffect(() => {
    if (!redraw && chartRef.current && options) {
      setOptions(chartRef.current, options);
    }
  }, [
    redraw,
    options
  ]);
  reactExports.useEffect(() => {
    if (!redraw && chartRef.current) {
      setLabels(chartRef.current.config.data, data.labels);
    }
  }, [
    redraw,
    data.labels
  ]);
  reactExports.useEffect(() => {
    if (!redraw && chartRef.current && data.datasets) {
      setDatasets(chartRef.current.config.data, data.datasets, datasetIdKey);
    }
  }, [
    redraw,
    data.datasets
  ]);
  reactExports.useEffect(() => {
    if (!chartRef.current) return;
    if (redraw) {
      destroyChart();
      setTimeout(renderChart);
    } else {
      chartRef.current.update(updateMode);
    }
  }, [
    redraw,
    options,
    data.labels,
    data.datasets,
    updateMode
  ]);
  reactExports.useEffect(() => {
    if (!chartRef.current) return;
    destroyChart();
    setTimeout(renderChart);
  }, [
    type
  ]);
  reactExports.useEffect(() => {
    renderChart();
    return () => destroyChart();
  }, []);
  return /* @__PURE__ */ jsxRuntimeExports.jsx("canvas", {
    ref: canvasRef,
    role: "img",
    height,
    width,
    ...canvasProps,
    children: fallbackContent
  });
}
const Chart = /* @__PURE__ */ reactExports.forwardRef(ChartComponent);
function createTypedChart(type, registerables) {
  Chart$1.register(registerables);
  return /* @__PURE__ */ reactExports.forwardRef((props, ref) => /* @__PURE__ */ jsxRuntimeExports.jsx(Chart, {
    ...props,
    ref,
    type
  }));
}
const Line = /* @__PURE__ */ createTypedChart("line", LineController);
const Bar = /* @__PURE__ */ createTypedChart("bar", BarController);
const MODELS = [{
  id: "B",
  label: "Model B — D1 Dataset (recommended)"
}, {
  id: "A",
  label: "Model A — D1+Lab, Attention LSTM"
}, {
  id: "C",
  label: "Model C — Lab Dataset"
}];
function playAlertSound() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext;
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
    gain.gain.exponentialRampToValueAtTime(1e-3, ctx.currentTime + 0.5);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.55);
  } catch {
  }
}
function SmartSurveil() {
  const [tab, setTab] = reactExports.useState("upload");
  const [ngrokUrl, setNgrokUrl] = reactExports.useState("");
  const [wsState, setWsState] = reactExports.useState("idle");
  const [kgState, setKgState] = reactExports.useState("idle");
  const [dbState, setDbState] = reactExports.useState("idle");
  const [model, setModel] = reactExports.useState("B");
  const [rtspModel, setRtspModel] = reactExports.useState("B");
  const [rtspUrl, setRtspUrl] = reactExports.useState("");
  const [file, setFile] = reactExports.useState(null);
  const [uploadStatus, setUploadStatus] = reactExports.useState("");
  const [rtspStatus, setRtspStatus] = reactExports.useState("");
  const [feedFrame, setFeedFrame] = reactExports.useState(null);
  const [feedSource, setFeedSource] = reactExports.useState("— no source —");
  const [progress, setProgress] = reactExports.useState(0);
  const [alerting, setAlerting] = reactExports.useState(false);
  const [activeVideoId, setActiveVideoId] = reactExports.useState(null);
  const [showReplay, setShowReplay] = reactExports.useState(false);
  const [videos, setVideos] = reactExports.useState([]);
  const [stats, setStats] = reactExports.useState(null);
  const [alerts, setAlerts] = reactExports.useState([]);
  const alertWsRef = reactExports.useRef(null);
  const streamWsRef = reactExports.useRef(null);
  const reconnectTimerRef = reactExports.useRef(null);
  const pingTimerRef = reactExports.useRef(null);
  const flashFeed = reactExports.useCallback(() => {
    setAlerting(false);
    requestAnimationFrame(() => setAlerting(true));
    window.setTimeout(() => setAlerting(false), 1600);
  }, []);
  const pushAlert = reactExports.useCallback((msg) => {
    setAlerts((prev) => [{
      ...msg,
      id: crypto.randomUUID(),
      ts: Date.now()
    }, ...prev].slice(0, 20));
  }, []);
  const loadStats = reactExports.useCallback(async () => {
    try {
      const r = await fetch("/api/stats");
      if (!r.ok) return;
      const d = await r.json();
      setStats(d);
    } catch {
    }
  }, []);
  const loadVideos = reactExports.useCallback(async () => {
    try {
      const r = await fetch("/api/videos");
      if (!r.ok) return;
      const d = await r.json();
      setVideos(d);
    } catch {
    }
  }, []);
  const checkHealth = reactExports.useCallback(async () => {
    try {
      const r = await fetch("/api/health");
      const d = await r.json();
      const ok = typeof d.kaggle === "object" && d.kaggle?.status === "ok";
      setKgState(ok ? "ok" : "warn");
      setDbState("ok");
    } catch {
      setKgState("err");
      setDbState("err");
    }
  }, []);
  const setKaggleUrl = reactExports.useCallback(async () => {
    if (!ngrokUrl.trim()) return;
    const fd = new FormData();
    fd.append("url", ngrokUrl.trim());
    try {
      await fetch("/api/kaggle-url", {
        method: "POST",
        body: fd
      });
    } catch {
    }
    checkHealth();
  }, [ngrokUrl, checkHealth]);
  const startInferStream = reactExports.useCallback((videoId) => {
    if (streamWsRef.current) {
      streamWsRef.current.close();
      streamWsRef.current = null;
    }
    setActiveVideoId(videoId);
    setFeedSource(`Video #${videoId} — Live Inference`);
    setShowReplay(false);
    setProgress(0);
    setFeedFrame(null);
    const ws = new WebSocket(`ws://${window.location.host}/ws/infer/${videoId}`);
    streamWsRef.current = ws;
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === "frame") {
          setFeedFrame(msg.frame);
          if (msg.total && msg.frame_idx) {
            setProgress(msg.frame_idx / msg.total * 100);
          }
        } else if (msg.type === "meta") {
          setFeedSource(`Video #${videoId} · ${msg.model} · ${msg.total} frames · ${Math.round(msg.fps)}fps`);
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
      }
    };
    ws.onerror = () => setUploadStatus("Stream connection error");
  }, [loadStats, loadVideos]);
  const uploadVideo = reactExports.useCallback(async () => {
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
        body: fd
      });
      const d = await r.json();
      setUploadStatus(`Video #${d.video_id} uploaded — connecting stream…`);
      window.setTimeout(() => startInferStream(d.video_id), 500);
    } catch (err) {
      setUploadStatus(`Upload failed: ${err.message}`);
    }
  }, [file, model, startInferStream]);
  const startRtsp = reactExports.useCallback(async () => {
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
        body: fd
      });
      const d = await r.json();
      setRtspStatus(d.ok ? `Streaming ${rtspUrl}` : d.message || "Error");
      if (d.ok) {
        setFeedSource("RTSP LIVE");
        setFeedFrame(null);
      }
    } catch (err) {
      setRtspStatus(`Failed: ${err.message}`);
    }
  }, [rtspUrl, rtspModel]);
  const stopRtsp = reactExports.useCallback(async () => {
    try {
      await fetch("/api/rtsp/stop", {
        method: "POST"
      });
    } catch {
    }
    setRtspStatus("Stopped");
    setFeedSource("— no source —");
    setFeedFrame(null);
  }, []);
  const stopStream = reactExports.useCallback(() => {
    if (streamWsRef.current) {
      streamWsRef.current.close();
      streamWsRef.current = null;
    }
    setFeedFrame(null);
    setFeedSource("— no source —");
    setShowReplay(false);
    setProgress(0);
  }, []);
  const replayVideo = reactExports.useCallback(() => {
    if (activeVideoId !== null) startInferStream(activeVideoId);
  }, [activeVideoId, startInferStream]);
  const dismissAlert = reactExports.useCallback((id) => {
    setAlerts((a) => a.filter((x) => x.id !== id));
  }, []);
  const clearAlerts = reactExports.useCallback(() => setAlerts([]), []);
  const selectVideo = reactExports.useCallback((v) => {
    if (v.status === "done" || v.status === "pending") {
      startInferStream(v.id);
    }
  }, [startInferStream]);
  reactExports.useEffect(() => {
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
        }, 2e4);
      };
      ws.onclose = () => {
        setWsState("err");
        if (pingTimerRef.current) {
          window.clearInterval(pingTimerRef.current);
          pingTimerRef.current = null;
        }
        reconnectTimerRef.current = window.setTimeout(connect, 3e3);
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
            setUploadStatus(`Video #${msg.video_id}: ${String(msg.status).toUpperCase()}`);
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
  reactExports.useEffect(() => {
    checkHealth();
    loadStats();
    loadVideos();
    const a = window.setInterval(loadStats, 2e4);
    const b = window.setInterval(loadVideos, 1e4);
    const c = window.setInterval(checkHealth, 3e4);
    return () => {
      window.clearInterval(a);
      window.clearInterval(b);
      window.clearInterval(c);
    };
  }, [checkHealth, loadStats, loadVideos]);
  const hourlyData = reactExports.useMemo(() => {
    const labels = stats?.hourly_today.map((x) => `${x.hour}:00`) ?? [];
    const data = stats?.hourly_today.map((x) => x.count) ?? [];
    return {
      labels,
      datasets: [{
        data,
        backgroundColor: "rgba(220, 38, 38, 0.65)",
        borderColor: "rgba(220, 38, 38, 1)",
        borderWidth: 1,
        borderRadius: 3
      }]
    };
  }, [stats]);
  const dailyData = reactExports.useMemo(() => {
    const labels = stats?.daily_last_7.map((x) => x.date.slice(5)) ?? [];
    const data = stats?.daily_last_7.map((x) => x.count) ?? [];
    return {
      labels,
      datasets: [{
        data,
        borderColor: "rgb(79, 70, 229)",
        backgroundColor: "rgba(79, 70, 229, 0.12)",
        tension: 0.35,
        fill: true,
        pointBackgroundColor: "rgb(79, 70, 229)",
        pointRadius: 3,
        borderWidth: 2
      }]
    };
  }, [stats]);
  const chartOpts = reactExports.useMemo(() => ({
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false
      },
      tooltip: {
        enabled: true
      }
    },
    scales: {
      x: {
        ticks: {
          color: "#64748b",
          font: {
            size: 10
          }
        },
        grid: {
          display: false
        }
      },
      y: {
        ticks: {
          color: "#64748b",
          font: {
            size: 10
          },
          stepSize: 1
        },
        grid: {
          color: "rgba(0,0,0,0.05)"
        },
        beginAtZero: true
      }
    }
  }), []);
  const highRisk = stats?.high_risk_hours?.length ? stats.high_risk_hours.map((h) => `${h}:00`).join(" · ") : "none detected";
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex h-screen flex-col bg-background text-foreground", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsxs("header", { className: "flex h-14 flex-shrink-0 items-center gap-4 border-b border-border bg-surface px-5", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex items-center gap-2", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex h-7 w-7 items-center justify-center rounded-md bg-primary text-primary-foreground", children: /* @__PURE__ */ jsxRuntimeExports.jsx(ShieldIcon, {}) }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[1.05rem] font-semibold tracking-tight", children: "Smart Surveil" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "ml-1 hidden rounded bg-muted px-1.5 py-0.5 text-[0.65rem] font-medium text-muted-foreground sm:inline", children: "v1.0" })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "ml-2 flex gap-1.5", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx(StatusPill, { label: "WS", state: wsState }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(StatusPill, { label: "Inference", state: kgState }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(StatusPill, { label: "DB", state: dbState })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "ml-auto flex items-center gap-2", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsx("input", { value: ngrokUrl, onChange: (e) => setNgrokUrl(e.target.value), placeholder: "https://xxxx.ngrok-free.app", className: "hidden w-[300px] rounded-md border border-border bg-background px-3 py-1.5 text-[0.78rem] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring md:block" }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: setKaggleUrl, className: "rounded-md bg-primary px-3.5 py-1.5 text-[0.78rem] font-medium text-primary-foreground transition hover:opacity-90", children: "Connect" })
      ] })
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "grid h-[calc(100vh-3.5rem)] grid-cols-[280px_1fr_320px] overflow-hidden", children: [
      /* @__PURE__ */ jsxRuntimeExports.jsxs("aside", { className: "flex flex-col overflow-y-auto border-r border-border bg-surface", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs(Section, { title: "Video Source", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "mb-3 inline-flex w-full rounded-md bg-muted p-0.5", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(TabBtn, { active: tab === "upload", onClick: () => setTab("upload"), children: "Upload" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(TabBtn, { active: tab === "rtsp", onClick: () => setTab("rtsp"), children: "RTSP" })
          ] }),
          tab === "upload" ? /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "space-y-2.5", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "Video file", children: /* @__PURE__ */ jsxRuntimeExports.jsx("input", { type: "file", accept: "video/*", onChange: (e) => setFile(e.target.files?.[0] ?? null), className: "block w-full text-[0.75rem] text-foreground file:mr-2 file:rounded-md file:border-0 file:bg-muted file:px-2.5 file:py-1.5 file:text-[0.72rem] file:font-medium file:text-foreground hover:file:bg-accent" }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "Model", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Select, { value: model, onChange: setModel, children: MODELS.map((m) => /* @__PURE__ */ jsxRuntimeExports.jsx("option", { value: m.id, children: m.label }, m.id)) }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: uploadVideo, className: "mt-1 flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-[0.8rem] font-medium text-primary-foreground transition hover:opacity-90", children: "▶ Run Inference" }),
            uploadStatus && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.72rem] text-muted-foreground", children: uploadStatus })
          ] }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "space-y-2.5", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "RTSP URL", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Input, { value: rtspUrl, onChange: setRtspUrl, placeholder: "rtsp://192.168.1.x:554/stream" }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsx(Field, { label: "Model", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Select, { value: rtspModel, onChange: setRtspModel, children: MODELS.map((m) => /* @__PURE__ */ jsxRuntimeExports.jsxs("option", { value: m.id, children: [
              m.id,
              " — ",
              m.label.split("—")[1]?.trim() ?? m.label
            ] }, m.id)) }) }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex gap-1.5", children: [
              /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: startRtsp, className: "flex-1 rounded-md bg-success px-3 py-1.5 text-[0.78rem] font-medium text-white transition hover:opacity-90", style: {
                background: "var(--success)"
              }, children: "▶ Start" }),
              /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: stopRtsp, className: "flex-1 rounded-md border border-border bg-background px-3 py-1.5 text-[0.78rem] font-medium text-foreground transition hover:bg-muted", children: "■ Stop" })
            ] }),
            rtspStatus && /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.72rem] text-muted-foreground", children: rtspStatus })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(Section, { title: "Statistics", children: /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "grid grid-cols-2 gap-2", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(StatBox, { n: stats?.today_total ?? "—", label: "Today" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(StatBox, { n: stats?.this_hour ?? "—", label: "This hour" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(StatBox, { n: stats?.total_all_time ?? "—", label: "All time" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(StatBox, { n: videos.length || "—", label: "Videos" }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "col-span-2 rounded-md border border-border bg-background p-2.5", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.62rem] font-medium uppercase tracking-wide text-muted-foreground", children: "High risk hours" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: `mt-0.5 text-[0.78rem] font-medium ${stats?.high_risk_hours?.length ? "text-destructive" : "text-muted-foreground"}`, children: highRisk })
          ] })
        ] }) }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(Section, { title: "Hourly activity (today)", children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-[100px]", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Bar, { data: hourlyData, options: chartOpts }) }) }),
        /* @__PURE__ */ jsxRuntimeExports.jsx(Section, { title: "Processed videos", children: videos.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.72rem] text-muted-foreground", children: "No videos yet" }) : /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "-mx-1", children: videos.slice(0, 12).map((v) => /* @__PURE__ */ jsxRuntimeExports.jsxs("button", { onClick: () => selectVideo(v), className: "flex w-full items-center justify-between gap-2 rounded-md px-1 py-2 text-left transition hover:bg-muted", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "min-w-0 flex-1", children: [
            /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "truncate text-[0.75rem] font-medium text-foreground", children: v.filename }),
            /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "text-[0.65rem] text-muted-foreground", children: [
              v.incidents,
              " incident",
              v.incidents === 1 ? "" : "s",
              " ·",
              " ",
              v.model
            ] })
          ] }),
          /* @__PURE__ */ jsxRuntimeExports.jsx(VideoStatusBadge, { status: v.status })
        ] }, v.id)) }) })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("section", { className: "flex flex-col overflow-hidden bg-background", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex flex-shrink-0 items-center gap-3 border-b border-border bg-surface px-4 py-2.5", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.78rem] font-semibold uppercase tracking-wide text-muted-foreground", children: "Live feed" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "truncate text-[0.78rem] font-medium text-foreground", children: feedSource }),
          /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "ml-auto flex gap-1.5", children: [
            showReplay && /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: replayVideo, className: "rounded-md border border-border bg-background px-2.5 py-1 text-[0.72rem] font-medium text-foreground transition hover:bg-muted", children: "↺ Replay" }),
            /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: stopStream, className: "rounded-md border border-border bg-background px-2.5 py-1 text-[0.72rem] font-medium text-foreground transition hover:bg-muted", children: "■ Stop" })
          ] })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-1 flex-shrink-0 bg-muted", children: /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-full bg-primary transition-[width] duration-200 ease-linear", style: {
          width: `${progress}%`
        } }) }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: `relative flex flex-1 items-center justify-center overflow-hidden bg-slate-900 ${alerting ? "alerting" : ""}`, children: feedFrame ? /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: `data:image/jpeg;base64,${feedFrame}`, alt: "live inference frame", className: "max-h-full max-w-full object-contain" }) : /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex flex-col items-center gap-3 text-center text-slate-400", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx(CameraIcon, {}),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.85rem] font-medium", children: "No feed active" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.72rem] text-slate-500", children: "Upload a video or connect an RTSP stream to begin" })
        ] }) }),
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex-shrink-0 border-t border-border bg-surface px-4 py-3", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "mb-2 text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground", children: "Daily incidents (last 7 days)" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "h-[110px]", children: /* @__PURE__ */ jsxRuntimeExports.jsx(Line, { data: dailyData, options: chartOpts }) })
        ] })
      ] }),
      /* @__PURE__ */ jsxRuntimeExports.jsxs("aside", { className: "flex flex-col overflow-hidden border-l border-border bg-surface", children: [
        /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "flex flex-shrink-0 items-center gap-2 border-b border-border px-4 py-3", children: [
          /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[0.95rem] font-semibold", children: "Alerts" }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: "rounded-full bg-destructive px-2 py-0.5 text-[0.68rem] font-semibold text-destructive-foreground", children: alerts.length }),
          /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: clearAlerts, className: "ml-auto rounded-md border border-border bg-background px-2 py-0.5 text-[0.7rem] font-medium text-muted-foreground transition hover:bg-muted hover:text-foreground", children: "Clear" })
        ] }),
        /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "flex flex-1 flex-col gap-2 overflow-y-auto p-3", children: alerts.length === 0 ? /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "py-10 text-center text-[0.78rem] text-muted-foreground", children: "No incidents detected" }) : alerts.map((a, i) => /* @__PURE__ */ jsxRuntimeExports.jsx(AlertCard, { alert: a, onDismiss: dismissAlert, isLatest: i === 0 }, a.id)) })
      ] })
    ] })
  ] });
}
function StatusPill({
  label,
  state
}) {
  const cfg = {
    idle: {
      dot: "bg-slate-300",
      text: "text-muted-foreground",
      pulse: ""
    },
    ok: {
      dot: "bg-success",
      text: "text-foreground",
      pulse: "dot-pulse"
    },
    warn: {
      dot: "bg-warning",
      text: "text-foreground",
      pulse: ""
    },
    err: {
      dot: "bg-destructive",
      text: "text-foreground",
      pulse: ""
    }
  }[state];
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "inline-flex items-center gap-1.5 rounded-full border border-border bg-background px-2.5 py-1 text-[0.68rem] font-medium", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: `h-1.5 w-1.5 rounded-full ${cfg.dot} ${cfg.pulse}`, style: {
      background: state === "ok" ? "var(--success)" : state === "warn" ? "var(--warning)" : state === "err" ? "var(--destructive)" : void 0
    } }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: cfg.text, children: label })
  ] });
}
function Section({
  title,
  children
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "border-b border-border px-4 py-3.5", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "mb-2.5 text-[0.68rem] font-semibold uppercase tracking-wide text-muted-foreground", children: title }),
    children
  ] });
}
function TabBtn({
  active,
  onClick,
  children
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick, className: `flex-1 rounded px-3 py-1 text-[0.78rem] font-medium transition ${active ? "bg-surface text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`, children });
}
function Field({
  label,
  children
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("label", { className: "mb-1 block text-[0.68rem] font-medium text-muted-foreground", children: label }),
    children
  ] });
}
function Input({
  value,
  onChange,
  placeholder
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("input", { type: "text", value, onChange: (e) => onChange(e.target.value), placeholder, className: "w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-[0.75rem] text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring" });
}
function Select({
  value,
  onChange,
  children
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsx("select", { value, onChange: (e) => onChange(e.target.value), className: "w-full rounded-md border border-border bg-background px-2.5 py-1.5 text-[0.75rem] text-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-ring", children });
}
function StatBox({
  n,
  label
}) {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "rounded-md border border-border bg-background p-2.5", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "text-[1.4rem] font-semibold leading-none text-foreground", children: n }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("div", { className: "mt-1 text-[0.62rem] font-medium uppercase tracking-wide text-muted-foreground", children: label })
  ] });
}
function VideoStatusBadge({
  status
}) {
  const map = {
    done: {
      cls: "bg-emerald-50 text-emerald-700 ring-emerald-200",
      label: "Done"
    },
    processing: {
      cls: "bg-amber-50 text-amber-700 ring-amber-200",
      label: "Proc"
    },
    failed: {
      cls: "bg-red-50 text-red-700 ring-red-200",
      label: "Fail"
    },
    pending: {
      cls: "bg-slate-50 text-slate-600 ring-slate-200",
      label: "Pend"
    }
  };
  const {
    cls,
    label
  } = map[status];
  return /* @__PURE__ */ jsxRuntimeExports.jsx("span", { className: `flex-shrink-0 rounded-full px-2 py-0.5 text-[0.62rem] font-medium ring-1 ring-inset ${cls}`, children: label });
}
function AlertCard({
  alert,
  onDismiss,
  isLatest
}) {
  const time = new Date(alert.ts).toLocaleTimeString();
  const src = alert.source === "rtsp" ? "RTSP Live" : `Video #${alert.video_id ?? "?"}`;
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: `slide-in relative rounded-lg border p-3 ${isLatest ? "border-destructive bg-red-50/60 shadow-sm" : "border-border bg-background"}`, children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("button", { onClick: () => onDismiss(alert.id), className: "absolute right-2 top-2 text-muted-foreground transition hover:text-foreground", "aria-label": "Dismiss", children: "✕" }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "text-[0.65rem] font-medium text-muted-foreground", children: [
      time,
      " · ",
      src
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "mt-1 text-[1.5rem] font-semibold leading-none text-destructive", children: [
      (alert.probability * 100).toFixed(1),
      "%"
    ] }),
    /* @__PURE__ */ jsxRuntimeExports.jsxs("div", { className: "mt-1 text-[0.68rem] text-muted-foreground", children: [
      "Track #",
      alert.track_id ?? "—",
      " · Model ",
      alert.model ?? "—",
      " · Frame",
      " ",
      alert.frame_index ?? "—"
    ] }),
    alert.snapshot && /* @__PURE__ */ jsxRuntimeExports.jsx("img", { src: `data:image/jpeg;base64,${alert.snapshot}`, alt: "snapshot", className: "mt-2 w-full rounded-md border border-border" })
  ] });
}
function ShieldIcon() {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("svg", { width: "14", height: "14", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "2.2", strokeLinecap: "round", strokeLinejoin: "round", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("path", { d: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("path", { d: "m9 12 2 2 4-4" })
  ] });
}
function CameraIcon() {
  return /* @__PURE__ */ jsxRuntimeExports.jsxs("svg", { width: "44", height: "44", viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: "1.4", strokeLinecap: "round", strokeLinejoin: "round", className: "opacity-50", children: [
    /* @__PURE__ */ jsxRuntimeExports.jsx("path", { d: "M14.5 4h-5L7 7H4a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2h-3l-2.5-3z" }),
    /* @__PURE__ */ jsxRuntimeExports.jsx("circle", { cx: "12", cy: "13", r: "4" })
  ] });
}
export {
  SmartSurveil as component
};
