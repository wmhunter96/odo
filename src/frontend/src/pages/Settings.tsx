import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { api } from "../api/client";
import { useTheme } from "../context/ThemeContext";
import type { AppSettings, Healthz, ImportPreview, Vehicle } from "../types";

const COMMON_TIMEZONES = [
  "UTC",
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "America/Anchorage",
  "Pacific/Honolulu",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Tokyo",
  "Australia/Sydney",
];

export default function Settings() {
  const { theme, setTheme } = useTheme();
  const [vehicle, setVehicle] = useState<Vehicle | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [backupInfo, setBackupInfo] = useState<Record<string, unknown> | null>(null);
  const [health, setHealth] = useState<Healthz | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getActiveVehicle().then(setVehicle);
    api.getSettings().then(setSettings);
    api.backupInfo().then(setBackupInfo).catch(() => {});
    api.healthz().then(setHealth).catch(() => {});
  }, []);

  async function onTimezoneChange(tz: string) {
    const updated = await api.updateSettings({ timezone: tz });
    setSettings(updated);
  }

  async function onFileChosen(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImportFile(file);
    setImportResult(null);
    const result = await api.previewImport(file);
    setPreview(result);
  }

  async function confirmImport() {
    if (!importFile) return;
    setImporting(true);
    try {
      const result = await api.commitImport(importFile);
      setImportResult(`Imported ${result.imported} record(s), skipped ${result.skipped}.`);
      setPreview(null);
      setImportFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    } finally {
      setImporting(false);
    }
  }

  return (
    <div>
      <h2 className="page-title">Settings</h2>

      <div className="card">
        <div className="card-title">Vehicle</div>
        <div style={{ fontWeight: 700, fontSize: "1.05rem" }}>{vehicle?.name ?? "—"}</div>
        <div style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: 4 }}>
          Odo tracks a single active vehicle in v1. Every fill-up is stored with a vehicle ID so
          multi-vehicle support can be added later without a database redesign.
        </div>
      </div>

      <div className="card">
        <div className="card-title">Data</div>
        <div className="field">
          <label>Import Historical CSV</label>
          <input ref={fileInputRef} type="file" accept=".csv,text/csv" onChange={onFileChosen} />
        </div>

        {preview && (
          <div style={{ marginBottom: 14 }}>
            <p>
              <strong>{preview.total} records detected</strong>
              <br />
              {preview.valid} valid · {preview.errors} error{preview.errors === 1 ? "" : "s"}
            </p>
            {preview.errors > 0 && (
              <div className="table-scroll" style={{ marginBottom: 10 }}>
                <table className="history-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Problem</th>
                    </tr>
                  </thead>
                  <tbody>
                    {preview.rows
                      .filter((r) => !r.is_valid)
                      .map((r) => (
                        <tr key={r.row_number}>
                          <td>{r.row_number}</td>
                          <td>{r.errors.join("; ")}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="btn-row">
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setPreview(null);
                  setImportFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
              >
                Cancel
              </button>
              <button className="btn btn-primary" onClick={confirmImport} disabled={importing || preview.valid === 0}>
                {importing ? "Importing…" : `Import ${preview.valid} Record${preview.valid === 1 ? "" : "s"}`}
              </button>
            </div>
          </div>
        )}

        {importResult && <div className="chip chip-source-ocr">{importResult}</div>}

        <hr className="section-divider" />

        <a className="btn btn-secondary btn-block" href={api.exportCsvUrl()} download>
          Export CSV
        </a>

        {backupInfo && (
          <div style={{ marginTop: 14, fontSize: "0.85rem", color: "var(--text-muted)" }}>
            <strong style={{ color: "var(--text)" }}>Backup Information</strong>
            <br />
            Everything lives under <code>{String(backupInfo.data_dir)}</code>. Back up that entire
            directory (database + photos) to fully restore Odo.
            <br />
            {String(backupInfo.photo_count)} photo file(s) stored.
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-title">Application</div>
        <div className="field">
          <label>Theme</label>
          <div className="theme-toggle-group">
            {(["light", "dark", "system"] as const).map((t) => (
              <button key={t} className={theme === t ? "active" : ""} onClick={() => setTheme(t)}>
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
        </div>
        <div className="field">
          <label>Timezone</label>
          <select value={settings?.timezone ?? "UTC"} onChange={(e) => onTimezoneChange(e.target.value)}>
            {COMMON_TIMEZONES.map((tz) => (
              <option key={tz} value={tz}>
                {tz}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-title">OCR</div>
        <div className="field">
          <label>Odometer Photo</label>
          <select value={settings?.ocr_engine ?? "paddleocr"} disabled>
            <option value="paddleocr">PaddleOCR PP-OCRv6 (local, CPU)</option>
          </select>
        </div>
        <div className="field">
          <label>Receipt Photo</label>
          <select value="paddleocr-vl" disabled>
            <option value="paddleocr-vl">PaddleOCR-VL-1.6 (local, CPU)</option>
          </select>
        </div>
      </div>

      <div className="card">
        <div className="card-title">About</div>
        {health ? (
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
            <div>
              Version <strong style={{ color: "var(--text)" }}>{health.version}</strong>
            </div>
            <div>
              Build{" "}
              <code style={{ color: "var(--text)" }}>
                {health.git_sha === "unknown" ? "unknown (local/dev build)" : health.git_sha.slice(0, 7)}
              </code>
            </div>
            {health.build_date !== "unknown" && <div>Built {new Date(health.build_date).toLocaleString()}</div>}
            <div style={{ marginTop: 8 }}>
              This is the single most reliable way to check whether a container update actually took
              effect — it's read directly from the running server, not cached anywhere.
            </div>
          </div>
        ) : (
          <div style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>Loading…</div>
        )}
      </div>
    </div>
  );
}
