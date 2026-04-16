import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

export default function ProbabilityGraph({
  probs,
  threshold,
  label,
  estimated,
}) {
  const isShoplifting = label === "Shoplifting";
  const color = isShoplifting ? "#ff6b6b" : "#69ff47";

  const data = probs.map((p, i) => ({
    frame: i + 1,
    probability: parseFloat(p.toFixed(4)),
  }));

  const CustomTooltip = ({ active, payload, coordinate }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-surface border border-border rounded-lg px-3 py-2 text-xs">
          <p className="text-muted">Frame {payload[0].payload.frame}</p>
          <p style={{ color }} className="font-bold">
            Prob: {payload[0].value.toFixed(4)}
          </p>
        </div>
      );
    }
    return null;
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <h3 className="text-white font-bold text-sm uppercase tracking-widest">
          📈 Frame Probability
        </h3>
        {estimated && (
          <span className="text-yellow-400 text-xs bg-yellow-900/30 border border-yellow-500/40 rounded px-2 py-0.5">
            * Probabilities are estimated (sigmoid ramp)
          </span>
        )}
      </div>

      <div className="bg-surface border border-border rounded-xl p-4">
        <ResponsiveContainer width="100%" height={240}>
          <LineChart
            data={data}
            margin={{ top: 8, right: 16, bottom: 8, left: 0 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#333" />
            <XAxis
              dataKey="frame"
              tick={{ fill: "#aaa", fontSize: 11 }}
              label={{
                value: "Frame",
                position: "insideBottom",
                offset: -4,
                fill: "#aaa",
                fontSize: 11,
              }}
            />
            <YAxis
              domain={[0, 1]}
              tick={{ fill: "#aaa", fontSize: 11 }}
              tickFormatter={(v) => v.toFixed(1)}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine
              y={threshold}
              stroke="#ff4444"
              strokeDasharray="6 3"
              label={{
                value: `Thr ${threshold}`,
                fill: "#ff4444",
                fontSize: 11,
                position: "right",
              }}
            />
            <Line
              type="monotone"
              dataKey="probability"
              stroke={color}
              strokeWidth={2.5}
              dot={{ r: 3, fill: color, strokeWidth: 0 }}
              activeDot={{ r: 5, fill: color }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
