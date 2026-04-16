import { useEffect, useState } from "react";

export default function ResultCard({ result }) {
  const {
    label,
    probability,
    threshold,
    model,
    dataset,
    inference_time_seconds,
  } = result;
  const isShoplifting = label === "Shoplifting";
  const [animWidth, setAnimWidth] = useState(0);

  useEffect(() => {
    const t = setTimeout(
      () => setAnimWidth(Math.round(probability * 100)),
      100,
    );
    return () => clearTimeout(t);
  }, [probability]);

  return (
    <div
      className={`rounded-2xl border p-6 space-y-5 transition-all duration-500 ${
        isShoplifting
          ? "border-shoplifting/50 bg-shoplifting/5"
          : "border-normal/50 bg-normal/5"
      }`}
    >
      {/* Label */}
      <div className="flex items-center gap-4 flex-wrap">
        <div
          className={`text-3xl md:text-4xl font-extrabold tracking-tight ${
            isShoplifting ? "text-shoplifting" : "text-normal"
          }`}
        >
          {isShoplifting ? "🚨 SHOPLIFTING DETECTED" : "✅ NORMAL ACTIVITY"}
        </div>
      </div>

      {/* Confidence */}
      <div>
        <span className="text-muted text-xs uppercase tracking-widest">
          Confidence Score
        </span>
        <div className="text-confidence text-4xl font-extrabold mt-1">
          {probability.toFixed(4)}
        </div>
      </div>

      {/* Probability bar */}
      <div>
        <div className="flex justify-between text-xs text-muted mb-1.5">
          <span>0%</span>
          <span>100%</span>
        </div>
        <div className="relative h-8 bg-black/50 rounded-full overflow-hidden border border-border">
          <div
            className={`h-full rounded-full transition-all duration-700 ease-out flex items-center justify-end pr-3 ${
              isShoplifting ? "bg-shoplifting" : "bg-normal"
            }`}
            style={{ width: `${animWidth}%` }}
          >
            <span className="text-black text-xs font-extrabold">
              {animWidth}%
            </span>
          </div>
        </div>
      </div>

      {/* Meta info */}
      <div className="flex flex-wrap gap-3 text-xs">
        <Meta label="Threshold" value={threshold} />
        <Meta label="Model" value={`Exp ${model}`} />
        <Meta label="Inference" value={`${inference_time_seconds}s`} />
        <Meta label="Dataset" value={dataset} />
      </div>
    </div>
  );
}

function Meta({ label, value }) {
  return (
    <div className="flex gap-1.5 bg-black/40 border border-border rounded-md px-2.5 py-1">
      <span className="text-muted">{label}:</span>
      <span className="text-white font-semibold">{value}</span>
    </div>
  );
}
