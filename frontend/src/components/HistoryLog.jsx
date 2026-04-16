export default function HistoryLog({ history, onClear }) {
  if (history.length === 0) return null;

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-white font-bold text-sm uppercase tracking-widest">
          🕒 Inference History
        </h3>
        <button
          onClick={onClear}
          className="text-xs text-red-400 hover:text-red-300 border border-red-500/40 hover:border-red-400 rounded px-2.5 py-1 transition"
        >
          🗑 Clear History
        </button>
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
        {history.map((entry, i) => {
          const isShop = entry.label === "Shoplifting";
          const d = new Date(entry.timestamp);
          const timeStr = d.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          });
          const dateStr = d.toLocaleDateString([], {
            month: "short",
            day: "numeric",
          });
          return (
            <div
              key={i}
              className="flex items-center justify-between bg-surface border border-border rounded-lg px-4 py-2.5 text-xs"
            >
              <div className="flex items-center gap-3 flex-wrap">
                <span className="text-muted">
                  {dateStr} {timeStr}
                </span>
                <span className="text-accent font-semibold">
                  Exp {entry.model}
                </span>
                <span className="text-muted truncate max-w-[140px]">
                  {entry.filename}
                </span>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span
                  className={`font-bold ${isShop ? "text-shoplifting" : "text-normal"}`}
                >
                  {isShop ? "🚨 Shoplifting" : "✅ Normal"}
                </span>
                <span className="text-confidence font-semibold">
                  {entry.confidence.toFixed(4)}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
