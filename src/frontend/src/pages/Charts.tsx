import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "../api/client";
import type { ChartsResponse } from "../types";

const AXIS_COLOR = "var(--text-muted)";
const GRID_COLOR = "var(--border)";
const LINE_COLOR = "#16a34a";
const BAR_COLOR = "#0ea5e9";

export default function Charts() {
  const [data, setData] = useState<ChartsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .charts()
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty-state">Couldn't load charts: {error}</div>;
  if (!data) return <div className="spinner" />;

  const hasAny =
    data.mpg_over_time.length || data.price_over_time.length || data.monthly_spend.length || data.monthly_miles.length;

  if (!hasAny) {
    return (
      <div>
        <h2 className="page-title">Charts</h2>
        <div className="empty-state">Add a few fill-ups to see trends here.</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">Charts</h2>

      <div className="card chart-card">
        <h3>MPG Over Time</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data.mpg_over_time}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: AXIS_COLOR }} minTickGap={30} />
            <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} width={36} domain={["dataMin - 5", "dataMax + 5"]} />
            <Tooltip formatter={(v: number) => `${v.toFixed(1)} MPG`} />
            <Line type="monotone" dataKey="value" stroke={LINE_COLOR} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card chart-card">
        <h3>Gas Price Over Time</h3>
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={data.price_over_time}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: AXIS_COLOR }} minTickGap={30} />
            <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} width={36} />
            <Tooltip formatter={(v: number) => `$${v.toFixed(3)}/gal`} />
            <Line type="monotone" dataKey="value" stroke={BAR_COLOR} strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="card chart-card">
        <h3>Monthly Fuel Spend</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.monthly_spend}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: AXIS_COLOR }} />
            <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} width={36} />
            <Tooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
            <Bar dataKey="value" fill={LINE_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card chart-card">
        <h3>Miles Driven by Month</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={data.monthly_miles}>
            <CartesianGrid stroke={GRID_COLOR} strokeDasharray="3 3" />
            <XAxis dataKey="label" tick={{ fontSize: 11, fill: AXIS_COLOR }} />
            <YAxis tick={{ fontSize: 11, fill: AXIS_COLOR }} width={36} />
            <Tooltip formatter={(v: number) => `${Math.round(v)} mi`} />
            <Bar dataKey="value" fill={BAR_COLOR} radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
