import { useMemo, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import PhotoCapture from "../components/PhotoCapture";
import WarningBanner from "../components/WarningBanner";
import { api } from "../api/client";
import type { DuplicateCandidate, OCRProcessResponse } from "../types";
import { formatDate, formatMoney, formatMpg, formatOdometer, nowDatetimeLocalValue, toDatetimeLocalValue } from "../format";

type Step = "odometer" | "receipt" | "confirm";

interface FormState {
  timestamp: string;
  odometer: string;
  gallons: string;
  price_per_gallon: string;
  fuel_total: string;
  station_brand: string;
  station_address: string;
  notes: string;
}

export default function NewFillUp() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("odometer");
  const [odometerFile, setOdometerFile] = useState<File | null>(null);
  const [receiptFile, setReceiptFile] = useState<File | null>(null);
  const [processing, setProcessing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [ocr, setOcr] = useState<OCRProcessResponse | null>(null);
  const [dupesDismissed, setDupesDismissed] = useState(false);
  // Off by default: an uploaded (as opposed to just-taken) photo should
  // keep whatever date/time OCR actually read off the receipt, not get
  // silently overridden with right-now. The switch next to the date field
  // is the explicit opt-in for "no, really, use the current time."
  const [useCurrentDateTime, setUseCurrentDateTime] = useState(false);
  const [form, setForm] = useState<FormState>({
    timestamp: toDatetimeLocalValue(null),
    odometer: "",
    gallons: "",
    price_per_gallon: "",
    fuel_total: "",
    station_brand: "",
    station_address: "",
    notes: "",
  });

  function updateField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleUseCurrentDateTime(next: boolean) {
    setUseCurrentDateTime(next);
    // Toggling on snaps to "now" immediately (and handleSave() re-snaps at
    // save time so it's accurate even if the user lingers on this screen);
    // toggling off restores whatever OCR actually read off the receipt,
    // not just whatever the field happened to show a moment ago.
    updateField("timestamp", next ? nowDatetimeLocalValue() : toDatetimeLocalValue(ocr?.timestamp));
  }

  async function handleOdometerContinue(file: File) {
    setOdometerFile(file);
    setStep("receipt");
  }

  async function handleReceiptContinue(file: File) {
    if (!odometerFile) return;
    setReceiptFile(file);
    setProcessing(true);
    setErrorMsg(null);
    try {
      const result = await api.processOCR(odometerFile, file);
      setOcr(result);
      setUseCurrentDateTime(false);
      setForm({
        timestamp: toDatetimeLocalValue(result.timestamp),
        odometer: result.odometer_value != null ? String(result.odometer_value) : "",
        gallons: result.gallons != null ? String(result.gallons) : "",
        price_per_gallon: result.price_per_gallon != null ? String(result.price_per_gallon) : "",
        fuel_total: result.fuel_total != null ? String(result.fuel_total) : "",
        station_brand: result.station_brand ?? "",
        station_address: result.station_address ?? "",
        notes: "",
      });
      setStep("confirm");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "OCR failed");
    } finally {
      setProcessing(false);
    }
  }

  const preview = useMemo(() => {
    const odometer = parseFloat(form.odometer);
    const gallons = parseFloat(form.gallons);
    const fuelTotal = parseFloat(form.fuel_total);
    const prev = ocr?.previous_odometer ?? null;
    if (Number.isNaN(odometer)) return null;
    const miles = prev != null && odometer > prev ? odometer - prev : null;
    const mpg = miles != null && gallons > 0 ? miles / gallons : null;
    const costPerMile = miles != null && !Number.isNaN(fuelTotal) ? fuelTotal / miles : null;
    return { previousOdometer: prev, miles, mpg, costPerMile };
  }, [form.odometer, form.gallons, form.fuel_total, ocr]);

  async function handleSave() {
    if (!odometerFile || !receiptFile) return;
    setSaving(true);
    setErrorMsg(null);
    try {
      const fd = new FormData();
      // Re-reads the clock right now rather than reusing whatever moment
      // the toggle was flipped at -- the user may have spent a while on
      // this screen adjusting other fields before hitting Save.
      const timestamp = useCurrentDateTime ? new Date() : new Date(form.timestamp);
      fd.append("timestamp", timestamp.toISOString());
      fd.append("odometer", form.odometer);
      fd.append("gallons", form.gallons);
      if (form.price_per_gallon) fd.append("price_per_gallon", form.price_per_gallon);
      if (form.fuel_total) fd.append("fuel_total", form.fuel_total);
      if (form.station_brand) fd.append("station_brand", form.station_brand);
      if (form.station_address) fd.append("station_address", form.station_address);
      if (form.notes) fd.append("notes", form.notes);
      fd.append("source", "ocr");
      if (ocr?.odometer_raw_text) fd.append("raw_odometer_ocr", ocr.odometer_raw_text);
      if (ocr?.receipt_raw_text) fd.append("raw_receipt_ocr", ocr.receipt_raw_text);
      fd.append("odometer_photo", odometerFile);
      fd.append("receipt_photo", receiptFile);
      await api.createFillUp(fd);
      navigate("/");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Could not save fill-up");
    } finally {
      setSaving(false);
    }
  }

  if (step === "odometer") {
    return (
      <div>
        <StepDots current={0} />
        <PhotoCapture key="odometer-capture" prompt="Take Odometer Photo" glyph="🚗" onContinue={handleOdometerContinue} />
      </div>
    );
  }

  if (step === "receipt") {
    return (
      <div>
        <StepDots current={1} />
        <PhotoCapture
          key="receipt-capture"
          prompt="Take Receipt Photo"
          glyph="🧾"
          onContinue={handleReceiptContinue}
          continueLabel="Continue"
          busy={processing}
        />
        {errorMsg && <WarningBanner message={errorMsg} />}
      </div>
    );
  }

  // step === "confirm"
  return (
    <div>
      <h2 className="page-title">New Fill-Up</h2>

      {ocr?.warnings.odometer && <WarningBanner message={ocr.warnings.odometer} />}
      {ocr?.warnings.mpg && <WarningBanner message={ocr.warnings.mpg} />}
      {ocr?.warnings.fuel_math && <WarningBanner message={ocr.warnings.fuel_math} />}
      {ocr?.warnings.receipt_fields.map((msg) => (
        <WarningBanner key={msg} message={msg} />
      ))}

      {ocr && ocr.duplicates.length > 0 && !dupesDismissed && (
        <div className="warning-banner" style={{ flexDirection: "column", alignItems: "stretch" }}>
          <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
            <span className="icon">⚠️</span>
            <span>
              <strong>Possible Duplicate Fill-Up</strong>
              <br />
              {ocr.duplicates.map((d: DuplicateCandidate) => (
                <span key={d.id}>
                  {formatDate(d.timestamp)} · {formatOdometer(d.odometer)} · {d.gallons.toFixed(3)} gal ·{" "}
                  {formatMoney(d.fuel_total)}
                </span>
              ))}
            </span>
          </div>
          <div className="btn-row">
            <Link className="btn btn-secondary" to={`/fillup/${ocr.duplicates[0].id}`}>
              View Existing
            </Link>
            <button className="btn btn-secondary" onClick={() => setDupesDismissed(true)}>
              Save Anyway
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <div className="field">
          <label>Odometer (mi)</label>
          <input
            type="number"
            inputMode="decimal"
            value={form.odometer}
            onChange={(e) => updateField("odometer", e.target.value)}
          />
        </div>
        <div className="field-row">
          <div className="field">
            <label>Gallons</label>
            <input
              type="number"
              step="0.001"
              inputMode="decimal"
              value={form.gallons}
              onChange={(e) => updateField("gallons", e.target.value)}
            />
          </div>
          <div className="field">
            <label>Price/Gal</label>
            <input
              type="number"
              step="0.001"
              inputMode="decimal"
              value={form.price_per_gallon}
              onChange={(e) => updateField("price_per_gallon", e.target.value)}
            />
          </div>
        </div>
        <div className="field">
          <label>Total</label>
          <input
            type="number"
            step="0.01"
            inputMode="decimal"
            value={form.fuel_total}
            onChange={(e) => updateField("fuel_total", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Station</label>
          <input
            type="text"
            value={form.station_brand}
            onChange={(e) => updateField("station_brand", e.target.value)}
          />
        </div>
        <div className="field">
          <label>Address</label>
          <input
            type="text"
            value={form.station_address}
            onChange={(e) => updateField("station_address", e.target.value)}
          />
        </div>
        <div className="field">
          <div className="field-label-row">
            <label>Date &amp; Time</label>
            <label className="switch">
              <input
                type="checkbox"
                checked={useCurrentDateTime}
                onChange={(e) => toggleUseCurrentDateTime(e.target.checked)}
              />
              <span className="switch-track">
                <span className="switch-thumb" />
              </span>
              Use current time
            </label>
          </div>
          <input
            type="datetime-local"
            value={form.timestamp}
            onChange={(e) => updateField("timestamp", e.target.value)}
            disabled={useCurrentDateTime}
          />
        </div>
        <div className="field">
          <label>Notes (optional)</label>
          <textarea rows={2} value={form.notes} onChange={(e) => updateField("notes", e.target.value)} />
        </div>
      </div>

      {preview && (
        <div className="card">
          <div className="metric-grid">
            <div className="metric">
              <div className="label">Previous Odometer</div>
              <div className="value">{formatOdometer(preview.previousOdometer)}</div>
            </div>
            <div className="metric">
              <div className="label">Miles Driven</div>
              <div className="value">{preview.miles != null ? Math.round(preview.miles).toLocaleString() : "—"}</div>
            </div>
            <div className="metric">
              <div className="label">MPG</div>
              <div className="value">{formatMpg(preview.mpg)}</div>
            </div>
            <div className="metric">
              <div className="label">Cost/Mile</div>
              <div className="value">{preview.costPerMile != null ? `$${preview.costPerMile.toFixed(3)}` : "—"}</div>
            </div>
          </div>
        </div>
      )}

      {errorMsg && <WarningBanner message={errorMsg} />}

      {ocr && (ocr.odometer_raw_text || ocr.receipt_raw_text) && (
        <details className="card" style={{ fontSize: "0.8rem" }}>
          <summary style={{ cursor: "pointer", fontWeight: 700 }}>Raw OCR text</summary>
          <div style={{ marginTop: 10, color: "var(--text-muted)" }}>
            If a field above looks wrong, this is exactly what OCR read from each photo —
            useful for spotting why a value didn't extract correctly.
          </div>
          <div className="field-row" style={{ marginTop: 10 }}>
            <div>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>Odometer photo</label>
              <pre className="ocr-raw-text">{ocr.odometer_raw_text || "(no text found)"}</pre>
            </div>
            <div>
              <label style={{ display: "block", fontWeight: 600, marginBottom: 4 }}>Receipt photo</label>
              <pre className="ocr-raw-text">{ocr.receipt_raw_text || "(no text found)"}</pre>
            </div>
          </div>
        </details>
      )}

      <div style={{ marginTop: 16 }}>
        <button className="btn btn-primary btn-block btn-lg" onClick={handleSave} disabled={saving}>
          {saving ? "Saving…" : "✓ Looks Good"}
        </button>
      </div>
    </div>
  );
}

function StepDots({ current }: { current: number }) {
  return (
    <div className="step-dots">
      {[0, 1, 2].map((i) => (
        <span key={i} className={i === current ? "active" : ""} />
      ))}
    </div>
  );
}
