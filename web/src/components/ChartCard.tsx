import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';

const COLORS = ['#3b82f6', '#16a34a', '#eab308', '#ef4444', '#8b5cf6', '#f97316', '#06b6d4', '#ec4899'];

export function TrendChart({ data, lines }: { data: Record<string, unknown>[]; lines: { key: string; color: string; yAxisId?: string }[] }) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} stroke="#94a3b8" />
        <YAxis tick={{ fontSize: 10 }} stroke="#94a3b8" />
        {lines.some(l => l.yAxisId) && <YAxis yAxisId="y1" orientation="right" tick={{ fontSize: 10 }} stroke="#94a3b8" />}
        <Tooltip />
        {lines.map(l => (
          <Line key={l.key} type="monotone" dataKey={l.key} stroke={l.color} strokeWidth={2} dot={false} yAxisId={l.yAxisId} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function DoughnutCard({ labels, data }: { labels: string[]; data: number[] }) {
  const chartData = labels.map((l, i) => ({ name: l, value: data[i] }));
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie data={chartData} dataKey="value" innerRadius={50} outerRadius={80}>
          {chartData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip />
      </PieChart>
    </ResponsiveContainer>
  );
}
