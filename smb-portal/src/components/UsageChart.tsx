import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { UsageSummary } from "../api/types";

type Props = {
  usage: UsageSummary;
};

export function UsageChart({ usage }: Props) {
  const data = [
    {
      name: "This period",
      qa_ask: usage.qa_ask_count,
      walkthrough: usage.walkthrough_grant_count,
      matched: usage.receipts_matched,
    },
  ];

  return (
    <div className="chart-wrap">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#c9d4c4" />
          <XAxis dataKey="name" stroke="#4a5a48" />
          <YAxis allowDecimals={false} stroke="#4a5a48" />
          <Tooltip />
          <Legend />
          <Bar dataKey="qa_ask" name="Q&A asks" fill="#1f6f5b" radius={[6, 6, 0, 0]} />
          <Bar
            dataKey="walkthrough"
            name="Walkthrough grants"
            fill="#c46b2c"
            radius={[6, 6, 0, 0]}
          />
          <Bar
            dataKey="matched"
            name="Receipts matched"
            fill="#2f4f6f"
            radius={[6, 6, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
