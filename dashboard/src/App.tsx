import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import type { Run } from "./types";

const COLORS = ["#38bdf8", "#34d399", "#f472b6", "#fbbf24", "#a78bfa", "#fb7185"];
const tipStyle = {
  background: "#0b0f17",
  border: "1px solid #243049",
  borderRadius: 8,
  fontSize: 12,
  color: "#e5ecf5",
};

const colorFor = (id: string, all: string[]) => COLORS[Math.max(0, all.indexOf(id)) % COLORS.length];
const shortTime = (iso: string) => iso.slice(5, 16).replace("T", " ");

export default function App() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}data/runs.json`)
      .then((r) => r.json())
      .then((data: Run[]) => {
        setRuns(data);
        setSelected(data[data.length - 1]?.run_id ?? "");
      })
      .catch((e) => setError(String(e)));
  }, []);

  const targetIds = useMemo(() => {
    const s = new Set<string>();
    runs.forEach((r) => r.targets.forEach((t) => s.add(t.target_id)));
    return [...s];
  }, [runs]);

  const drift = useMemo(
    () =>
      runs.map((r) => {
        const row: Record<string, number | string> = { name: r.notes || shortTime(r.created_at) };
        r.targets.forEach((t) => (row[t.target_id] = t.mean_score));
        return row;
      }),
    [runs]
  );

  const regressions = useMemo(() => {
    let count = 0;
    for (let i = 1; i < runs.length; i++) {
      const prev = Object.fromEntries(runs[i - 1].targets.map((t) => [t.target_id, t.mean_score]));
      const dropped = runs[i].targets.some(
        (t) => (prev[t.target_id] ?? t.mean_score) - t.mean_score > 0.02
      );
      if (dropped) count++;
    }
    return count;
  }, [runs]);

  if (error)
    return (
      <div className="wrap">
        <p className="error">Failed to load data/runs.json — {error}</p>
        <p className="muted">Run <span className="mono">promptproof export</span> first.</p>
      </div>
    );
  if (runs.length === 0) return <div className="wrap"><p className="muted">Loading…</p></div>;

  const current = runs.find((r) => r.run_id === selected) ?? runs[runs.length - 1];
  const sorted = [...current.targets].sort((a, b) => b.mean_score - a.mean_score);
  const best = sorted[0];
  const bestValue =
    [...current.targets].filter((t) => t.pass_rate >= 1).sort((a, b) => a.total_cost_usd - b.total_cost_usd)[0] ??
    best;
  const scatter = current.targets.map((t) => ({
    x: +(t.total_cost_usd * 1000).toFixed(3),
    y: t.mean_score,
    z: 100,
    name: t.target_id,
  }));

  return (
    <div className="wrap">
      <header>
        <div>
          <h1>
            Prompt<span className="accent">Proof</span>
          </h1>
          <p className="sub">
            LLM eval &amp; regression dashboard · <span className="mono">{current.suite_name}</span>
          </p>
        </div>
        <label className="picker">
          <span>run</span>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {runs.map((r) => (
              <option key={r.run_id} value={r.run_id}>
                {(r.notes || shortTime(r.created_at)) + " · " + r.run_id.slice(-4)}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="kpis">
        <Kpi label="Best score" value={best.mean_score.toFixed(3)} sub={best.target_id} accent="#34d399" />
        <Kpi
          label="Best value · 100% pass"
          value={`$${bestValue.total_cost_usd.toFixed(4)}`}
          sub={bestValue.target_id}
          accent="#38bdf8"
        />
        <Kpi label="Runs tracked" value={String(runs.length)} sub="history" accent="#a78bfa" />
        <Kpi
          label="Regressions caught"
          value={String(regressions)}
          sub="score drop > 2%"
          accent={regressions ? "#fb7185" : "#34d399"}
        />
      </section>

      <section className="grid2">
        <Card title="Score drift across runs">
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={drift} margin={{ left: -12, right: 12, top: 8 }}>
              <CartesianGrid stroke="#1b2433" strokeDasharray="3 3" />
              <XAxis dataKey="name" tick={{ fill: "#7d8aa0", fontSize: 10 }} angle={-12} textAnchor="end" height={54} />
              <YAxis domain={[0.5, 1]} tick={{ fill: "#7d8aa0", fontSize: 11 }} />
              <Tooltip contentStyle={tipStyle} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              {targetIds.map((id) => (
                <Line
                  key={id}
                  type="monotone"
                  dataKey={id}
                  stroke={colorFor(id, targetIds)}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  activeDot={{ r: 5 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
          <p className="caption">The dip is a broken prompt (category→type) caught by the eval gate, then reverted.</p>
        </Card>

        <Card title="Cost vs quality · selected run">
          <ResponsiveContainer width="100%" height={300}>
            <ScatterChart margin={{ left: -12, right: 12, top: 8, bottom: 18 }}>
              <CartesianGrid stroke="#1b2433" strokeDasharray="3 3" />
              <XAxis
                type="number"
                dataKey="x"
                name="cost"
                tick={{ fill: "#7d8aa0", fontSize: 11 }}
                label={{ value: "cost per run (milli-$)", position: "insideBottom", offset: -8, fill: "#7d8aa0", fontSize: 11 }}
              />
              <YAxis type="number" dataKey="y" name="score" domain={[0.5, 1]} tick={{ fill: "#7d8aa0", fontSize: 11 }} />
              <ZAxis type="number" dataKey="z" range={[140, 140]} />
              <Tooltip contentStyle={tipStyle} cursor={{ strokeDasharray: "3 3" }} formatter={(v: number, n: string) => [n === "cost" ? `${v} m$` : v, n]} />
              <Scatter data={scatter} isAnimationActive={false}>
                {scatter.map((p, i) => (
                  <Cell key={i} fill={colorFor(p.name, targetIds)} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
          <p className="caption">Up-and-left wins: high score, low cost. Few-shot on the small model is the value pick.</p>
        </Card>
      </section>

      <section>
        <Card title={`Leaderboard · ${current.notes || shortTime(current.created_at)}`}>
          <table>
            <thead>
              <tr>
                <th>Target</th>
                <th>Score</th>
                <th>Pass</th>
                <th>Cost</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((t) => (
                <tr key={t.target_id}>
                  <td className="mono" style={{ color: colorFor(t.target_id, targetIds) }}>
                    {t.target_id}
                  </td>
                  <td>
                    <div className="scorecell">
                      <div className="bar">
                        <span style={{ width: `${t.mean_score * 100}%`, background: colorFor(t.target_id, targetIds) }} />
                      </div>
                      <b>{t.mean_score.toFixed(3)}</b>
                    </div>
                  </td>
                  <td className={t.pass_rate >= 1 ? "ok" : t.pass_rate <= 0 ? "bad" : ""}>
                    {Math.round(t.pass_rate * 100)}%
                  </td>
                  <td>${t.total_cost_usd.toFixed(4)}</td>
                  <td>{Math.round(t.mean_latency_ms)} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </section>

      <footer>
        Generated by <span className="mono">promptproof export</span> · built with Claude Code
      </footer>
    </div>
  );
}

function Kpi({ label, value, sub, accent }: { label: string; value: string; sub: string; accent: string }) {
  return (
    <div className="kpi">
      <span className="kpi-label">{label}</span>
      <span className="kpi-value" style={{ color: accent }}>
        {value}
      </span>
      <span className="kpi-sub mono">{sub}</span>
    </div>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {children}
    </div>
  );
}
