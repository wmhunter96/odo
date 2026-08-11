import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { FillUp, FillUpUpdate } from "../types";
import {
  formatCostPerMile,
  formatDate,
  formatGallons,
  formatMoney,
  formatMpg,
  formatOdometer,
  formatPricePerGallon,
  formatTime,
  toDatetimeLocalValue,
} from "../format";

export default function FillUpDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [fillup, setFillup] = useState<FillUp | null>(null);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!id) return;
    api
      .getFillUp(Number(id))
      .then((f) => {
        setFillup(f);
        setForm({
          timestamp: toDatetimeLocalValue(f.timestamp),
          odometer: String(f.odometer),
          gallons: String(f.gallons),
          price_per_gallon: f.price_per_gallon != null ? String(f.price_per_gallon) : "",
          fuel_total: f.fuel_total != null ? String(f.fuel_total) : "",
          station_brand: f.station_brand ?? "",
          station_address: f.station_address ?? "",
          notes: f.notes ?? "",
        });
      })
      .catch((e) => setError(e.message));
  }, [id]);

  if (error) return <div className="empty-state">{error}</div>;
  if (!fillup) return <div className="spinner" />;

  async function handleSave() {
    if (!fillup) return;
    setSaving(true);
    try {
      const payload: FillUpUpdate = {
        timestamp: new Date(form.timestamp).toISOString(),
        odometer: parseFloat(form.odometer),
        gallons: parseFloat(form.gallons),
        price_per_gallon: form.price_per_gallon ? parseFloat(form.price_per_gallon) : null,
        fuel_total: form.fuel_total ? parseFloat(form.fuel_total) : null,
        station_brand: form.station_brand || null,
        station_address: form.station_address || null,
        notes: form.notes || null,
      };
      const updated = await api.updateFillUp(fillup.id, payload);
      setFillup(updated);
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not save changes");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!fillup) return;
    if (!confirm("Delete this fill-up? This cannot be undone.")) return;
    await api.deleteFillUp(fillup.id);
    navigate("/history");
  }

  if (editing) {
    return (
      <div>
        <h2 className="page-title">Edit Fill-Up</h2>
        <div className="card">
          <div className="field">
            <label>Odometer (mi)</label>
            <input
              type="number"
              value={form.odometer}
              onChange={(e) => setForm({ ...form, odometer: e.target.value })}
            />
          </div>
          <div className="field-row">
            <div className="field">
              <label>Gallons</label>
              <input
                type="number"
                step="0.001"
                value={form.gallons}
                onChange={(e) => setForm({ ...form, gallons: e.target.value })}
              />
            </div>
            <div className="field">
              <label>Price/Gal</label>
              <input
                type="number"
                step="0.001"
                value={form.price_per_gallon}
                onChange={(e) => setForm({ ...form, price_per_gallon: e.target.value })}
              />
            </div>
          </div>
          <div className="field">
            <label>Total</label>
            <input
              type="number"
              step="0.01"
              value={form.fuel_total}
              onChange={(e) => setForm({ ...form, fuel_total: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Station</label>
            <input
              type="text"
              value={form.station_brand}
              onChange={(e) => setForm({ ...form, station_brand: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Address</label>
            <input
              type="text"
              value={form.station_address}
              onChange={(e) => setForm({ ...form, station_address: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Date &amp; Time</label>
            <input
              type="datetime-local"
              value={form.timestamp}
              onChange={(e) => setForm({ ...form, timestamp: e.target.value })}
            />
          </div>
          <div className="field">
            <label>Notes</label>
            <textarea rows={2} value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </div>
        </div>
        <div className="btn-row" style={{ marginTop: 14 }}>
          <button className="btn btn-secondary" onClick={() => setEditing(false)} disabled={saving}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2 className="page-title">
        {formatDate(fillup.timestamp)} <span className="chip">{formatTime(fillup.timestamp)}</span>
        {fillup.source === "ocr" && <span className="chip chip-source-ocr">OCR</span>}
      </h2>

      <div className="card">
        <div className="metric-grid">
          <div className="metric">
            <div className="label">Odometer</div>
            <div className="value">{formatOdometer(fillup.odometer)}</div>
          </div>
          <div className="metric">
            <div className="label">Miles Driven</div>
            <div className="value">
              {fillup.miles_driven != null ? Math.round(fillup.miles_driven).toLocaleString() : "—"}
            </div>
          </div>
          <div className="metric">
            <div className="label">Gallons</div>
            <div className="value">{formatGallons(fillup.gallons)}</div>
          </div>
          <div className="metric">
            <div className="label">MPG</div>
            <div className="value">{formatMpg(fillup.mpg)}</div>
          </div>
          <div className="metric">
            <div className="label">Total</div>
            <div className="value">{formatMoney(fillup.fuel_total)}</div>
          </div>
          <div className="metric">
            <div className="label">Price/Gal</div>
            <div className="value">{formatPricePerGallon(fillup.price_per_gallon)}</div>
          </div>
          <div className="metric">
            <div className="label">Cost/Mile</div>
            <div className="value">{formatCostPerMile(fillup.cost_per_mile)}</div>
          </div>
          <div className="metric">
            <div className="label">Station</div>
            <div className="value">{fillup.station_brand ?? "—"}</div>
          </div>
        </div>
        {fillup.station_address && (
          <div style={{ marginTop: 10, color: "var(--text-muted)", fontSize: "0.9rem" }}>
            {fillup.station_address}
          </div>
        )}
        {fillup.notes && (
          <div style={{ marginTop: 10, fontSize: "0.9rem" }}>
            <strong>Notes:</strong> {fillup.notes}
          </div>
        )}
      </div>

      {(fillup.odometer_photo_path || fillup.receipt_photo_path) && (
        <div className="photo-thumb-row">
          {fillup.odometer_photo_path && (
            <a href={api.photoUrl(fillup.id, "odometer")} target="_blank" rel="noreferrer">
              <img src={api.photoUrl(fillup.id, "odometer", true)} alt="Odometer" />
            </a>
          )}
          {fillup.receipt_photo_path && (
            <a href={api.photoUrl(fillup.id, "receipt")} target="_blank" rel="noreferrer">
              <img src={api.photoUrl(fillup.id, "receipt", true)} alt="Receipt" />
            </a>
          )}
        </div>
      )}

      <div className="btn-row" style={{ marginTop: 16 }}>
        <button className="btn btn-secondary" onClick={() => setEditing(true)}>
          Edit
        </button>
        <button className="btn btn-danger" onClick={handleDelete}>
          Delete
        </button>
      </div>
    </div>
  );
}
