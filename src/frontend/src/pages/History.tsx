import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { FillUp } from "../types";
import { formatDate, formatMoney, formatMpg, formatOdometer } from "../format";

export default function History() {
  const [fillups, setFillups] = useState<FillUp[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listFillUps()
      .then(setFillups)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="empty-state">Couldn't load history: {error}</div>;
  if (!fillups) return <div className="spinner" />;

  if (fillups.length === 0) {
    return (
      <div>
        <h2 className="page-title">History</h2>
        <div className="empty-state">No fill-ups recorded yet.</div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">History</h2>
      {fillups.map((f) => (
        <Link key={f.id} to={`/fillup/${f.id}`} className="fillup-card">
          <div>
            <div className="main-line">{formatDate(f.timestamp)}</div>
            <div className="sub-line">
              {formatOdometer(f.odometer)}
              {f.miles_driven != null ? ` · ${Math.round(f.miles_driven)} mi driven` : ""}
              {f.station_brand ? ` · ${f.station_brand}` : ""}
            </div>
          </div>
          <div className="right">
            <div className="mpg-badge">{formatMpg(f.mpg)}</div>
            <div className="sub-line">{formatMoney(f.fuel_total)}</div>
          </div>
        </Link>
      ))}
    </div>
  );
}
