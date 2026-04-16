import { MODEL_META } from "./ModelSelector.jsx";
import ProbabilityGraph from "./ProbabilityGraph.jsx";

export default function CompareView({ data }) {
  const { results, majority_vote } = data;
  const shopCount = results.filter((r) => r.label === "Shoplifting").length;
  const isMajorityShop = majority_vote === "Shoplifting";

  return (
    <div className="space-y-6">
      <h2 className="text-white font-extrabold text-xl uppercase tracking-widest">
        ⚖️ Model Comparison
      </h2>

      {/* 3 cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {results.map((r) => {
          const isShop = r.label === "Shoplifting";
          const meta = MODEL_META[r.model];
          return (
            <div
              key={r.model}
              className={`rounded-xl border p-5 space-y-3 ${
                isShop
                  ? "border-shoplifting/50 bg-shoplifting/5"
                  : "border-normal/50 bg-normal/5"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-accent font-bold text-sm">
                  Exp {r.model}
                </span>
                {r.model === "A" && (
                  <span className="text-yellow-400 text-xs border border-yellow-500/40 rounded px-1.5 py-0.5">
                    ★ Best
                  </span>
                )}
              </div>
              <div
                className={`text-2xl font-extrabold ${isShop ? "text-shoplifting" : "text-normal"}`}
              >
                {isShop ? "🚨 SHOPLIFTING" : "✅ NORMAL"}
              </div>
              <div className="text-confidence text-2xl font-bold">
                {r.probability.toFixed(4)}
              </div>
              {/* Mini prob bar */}
              <div className="h-3 bg-black/50 rounded-full overflow-hidden border border-border">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${isShop ? "bg-shoplifting" : "bg-normal"}`}
                  style={{ width: `${Math.round(r.probability * 100)}%` }}
                />
              </div>
              <div className="text-muted text-xs space-y-0.5">
                <p>
                  Threshold: {r.threshold} | {r.inference_time_seconds}s
                </p>
                <p>Dataset: {meta.dataset}</p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Comparison table */}
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-surface">
            <tr className="text-muted text-xs uppercase tracking-wider">
              {[
                "Model",
                "Label",
                "Confidence",
                "Threshold",
                "F1",
                "ROC-AUC",
                "Time",
              ].map((h) => (
                <th
                  key={h}
                  className="px-4 py-3 text-left border-b border-border"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((r) => {
              const meta = MODEL_META[r.model];
              const isShop = r.label === "Shoplifting";
              return (
                <tr
                  key={r.model}
                  className="border-b border-border hover:bg-white/5 transition"
                >
                  <td className="px-4 py-3 text-accent font-bold">
                    Exp {r.model}
                  </td>
                  <td
                    className={`px-4 py-3 font-semibold ${isShop ? "text-shoplifting" : "text-normal"}`}
                  >
                    {r.label}
                  </td>
                  <td className="px-4 py-3 text-confidence">
                    {r.probability.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-white">{r.threshold}</td>
                  <td className="px-4 py-3 text-white">{meta.f1.toFixed(4)}</td>
                  <td className="px-4 py-3 text-white">
                    {meta.rocAuc.toFixed(4)}
                  </td>
                  <td className="px-4 py-3 text-white">
                    {r.inference_time_seconds}s
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Majority vote banner */}
      <div
        className={`rounded-xl border p-5 text-center text-xl font-extrabold tracking-wide ${
          isMajorityShop
            ? "border-shoplifting/60 bg-shoplifting/10 text-shoplifting"
            : "border-normal/60 bg-normal/10 text-normal"
        }`}
      >
        {shopCount}/3 models say:{" "}
        {isMajorityShop ? "🚨 SHOPLIFTING" : "✅ NORMAL"}
      </div>

      {/* Frame probability graphs for all 3 */}
      <div className="space-y-4">
        <h3 className="text-white font-bold text-sm uppercase tracking-widest">
          📈 Frame Probability per Model
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {results.map((r) => (
            <div
              key={r.model}
              className="bg-surface border border-border rounded-xl p-3"
            >
              <p className="text-accent text-xs font-bold mb-2">
                Exp {r.model}
              </p>
              <ProbabilityGraph
                probs={r.frame_probabilities}
                threshold={r.threshold}
                label={r.label}
                estimated={r.frame_prob_estimated}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
