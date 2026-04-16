const MODEL_META = {
  A: {
    label: "Exp A — Combined D1+Lab",
    tag: "★ Best Overall",
    threshold: 0.83,
    rocAuc: 0.9524,
    f1: 0.9286,
    accuracy: 0.9268,
    dataset: "Combined D1+Lab",
    train: 654,
    val: 164,
  },
  B: {
    label: "Exp B — D1 Only",
    tag: "",
    threshold: 0.37,
    rocAuc: 0.7937,
    f1: 0.7651,
    accuracy: 0.7266,
    dataset: "D1 Only",
    train: 508,
    val: 128,
  },
  C: {
    label: "Exp C — Lab Only",
    tag: "",
    threshold: 0.78,
    rocAuc: 0.9708,
    f1: 0.9189,
    accuracy: 0.9189,
    dataset: "Lab Only",
    train: 145,
    val: 37,
  },
};

export { MODEL_META };

export default function ModelSelector({ selected, onChange }) {
  const meta = MODEL_META[selected];

  return (
    <div className="flex flex-col md:flex-row md:items-center gap-4">
      {/* Dropdown */}
      <div className="flex items-center gap-3">
        <span className="text-muted text-xs uppercase tracking-widest font-bold">
          Model
        </span>
        <select
          value={selected}
          onChange={(e) => onChange(e.target.value)}
          className="bg-black border border-border text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-accent cursor-pointer"
        >
          {Object.entries(MODEL_META).map(([key, m]) => (
            <option key={key} value={key}>
              {m.label} {m.tag ? `(${m.tag})` : ""} | thr: {m.threshold}
            </option>
          ))}
        </select>
      </div>

      {/* Stats bar */}
      <div className="flex flex-wrap gap-3 text-xs">
        <Stat label="ROC-AUC" value={meta.rocAuc.toFixed(4)} />
        <Stat label="F1" value={meta.f1.toFixed(4)} />
        <Stat label="Accuracy" value={meta.accuracy.toFixed(4)} />
        <Stat label="Threshold" value={meta.threshold} />
        <Stat label="Dataset" value={meta.dataset} />
        <Stat label="Train/Val" value={`${meta.train}/${meta.val}`} />
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div className="flex items-center gap-1.5 bg-black/50 border border-border rounded-md px-2.5 py-1">
      <span className="text-muted">{label}:</span>
      <span className="text-accent font-semibold">{value}</span>
    </div>
  );
}
