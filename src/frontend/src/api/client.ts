import type {
  AppSettings,
  ChartsResponse,
  DashboardStats,
  FillUp,
  FillUpUpdate,
  ImportPreview,
  LifetimeStats,
  OCRProcessResponse,
  Vehicle,
} from "../types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getActiveVehicle: () => request<Vehicle>("/api/vehicles/active"),
  updateVehicle: (id: number, payload: Partial<Vehicle>) =>
    request<Vehicle>(`/api/vehicles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  listFillUps: (limit = 200) => request<FillUp[]>(`/api/fillups?limit=${limit}`),
  getFillUp: (id: number) => request<FillUp>(`/api/fillups/${id}`),
  updateFillUp: (id: number, payload: FillUpUpdate) =>
    request<FillUp>(`/api/fillups/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteFillUp: (id: number) => request<void>(`/api/fillups/${id}`, { method: "DELETE" }),

  createFillUp: (form: FormData) =>
    request<FillUp>("/api/fillups", { method: "POST", body: form }),

  processOCR: (odometerImage: File, receiptImage: File) => {
    const form = new FormData();
    form.append("odometer_image", odometerImage);
    form.append("receipt_image", receiptImage);
    return request<OCRProcessResponse>("/api/ocr/process", { method: "POST", body: form });
  },

  dashboardStats: () => request<DashboardStats>("/api/stats/dashboard"),
  lifetimeStats: () => request<LifetimeStats>("/api/stats/lifetime"),
  charts: () => request<ChartsResponse>("/api/charts"),

  previewImport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportPreview>("/api/import/csv/preview", { method: "POST", body: form });
  },
  commitImport: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ imported: number; skipped: number }>("/api/import/csv/commit", {
      method: "POST",
      body: form,
    });
  },
  exportCsvUrl: () => "/api/export/csv",

  getSettings: () => request<AppSettings>("/api/settings"),
  updateSettings: (payload: Partial<AppSettings>) =>
    request<AppSettings>("/api/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  backupInfo: () => request<Record<string, unknown>>("/api/settings/backup-info"),

  photoUrl: (fillupId: number, kind: "odometer" | "receipt", thumbnail = false) =>
    `/api/fillups/${fillupId}/photo/${kind}${thumbnail ? "?thumbnail=true" : ""}`,
};
