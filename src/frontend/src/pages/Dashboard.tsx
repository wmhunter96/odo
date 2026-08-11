import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardStats, Vehicle } from "../types";
import {
  formatDate,
  formatGallons,
  formatMoney,
  formatMpg,
  formatOdometer,
  formatPricePerGallon,
} from "../format";

export default function Dashboard() {
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([api.getActiveVehicle(), api.dashboardStats()])
      .then(([v, s]) => {
        setVehicle(v);
        setStats(s);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="spinner" />;
  if (error) return <div className="empty-state">Couldn't load dashboard: {error}</div>;

  const last = stats?.last_fillup ?? null;

  return (
    <div>
      <div className="vehicle-name">{vehicle?.name}</div>

      <Link to="/new-fillup" className="btn btn-primary btn-lg btn-block" style={{ marginBottom: 18 }}>
        + NEW FILL-UP
      </Link>

      <div className="card">
        <div className="card-title">Last Fill-Up</div>
        {last ? (
          <>
            <div className="last-fillup-headline">
              <span className="date">{formatDate(last.timestamp)}</span>
              <span>{formatOdometer(last.odometer)}</span>
            </div>
            <div className="metric-grid">
              <div className="metric">
                <div className="label">Gallons</div>
                <div className="value">{formatGallons(last.gallons)}</div>
              </div>
              <div className="metric">
                <div className="label">Total</div>
                <div className="value">{formatMoney(last.fuel_total)}</div>
              </div>
              <div className="metric">
                <div className="label">MPG</div>
                <div className="value">{formatMpg(last.mpg)}</div>
              </div>
              <div className="metric">
                <div className="label">Price/Gal</div>
                <div className="value">{formatPricePerGallon(last.price_per_gallon)}</div>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">No fill-ups yet. Tap "New Fill-Up" to add your first one.</div>
        )}
      </div>

      <hr className="section-divider" />

      <div className="card-title" style={{ margin: "0 0 10px" }}>
        This Month
      </div>
      <div className="stat-tiles">
        <div className="stat-tile">
          <div className="label">Spent</div>
          <div className="value">{formatMoney(stats?.month_spend)}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Miles Driven</div>
          <div className="value">{Math.round(stats?.month_miles ?? 0).toLocaleString()}</div>
        </div>
        <div className="stat-tile" style={{ gridColumn: "1 / -1" }}>
          <div className="label">MPG</div>
          <div className="value">{formatMpg(stats?.month_mpg)}</div>
        </div>
      </div>

      <hr className="section-divider" />

      <div className="card-title" style={{ margin: "0 0 10px" }}>
        Lifetime
      </div>
      <div className="stat-tiles">
        <div className="stat-tile">
          <div className="label">Average MPG</div>
          <div className="value">{formatMpg(stats?.lifetime_average_mpg)}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Total Miles</div>
          <div className="value">{Math.round(stats?.lifetime_total_miles ?? 0).toLocaleString()}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Total Fuel Cost</div>
          <div className="value">{formatMoney(stats?.lifetime_total_fuel_cost)}</div>
        </div>
        <div className="stat-tile">
          <div className="label">Avg Gas Price</div>
          <div className="value">{formatPricePerGallon(stats?.lifetime_average_price)}</div>
        </div>
      </div>
    </div>
  );
}
