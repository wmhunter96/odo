export interface Vehicle {
  id: number;
  name: string;
  year: number | null;
  make: string | null;
  model: string | null;
  trim: string | null;
  is_active: boolean;
}

export interface FillUp {
  id: number;
  vehicle_id: number;
  timestamp: string;
  odometer: number;
  gallons: number;
  price_per_gallon: number | null;
  fuel_total: number | null;
  station_brand: string | null;
  station_address: string | null;
  latitude: number | null;
  longitude: number | null;
  odometer_photo_path: string | null;
  receipt_photo_path: string | null;
  raw_odometer_ocr: string | null;
  raw_receipt_ocr: string | null;
  ocr_confidence: number | null;
  notes: string | null;
  source: string;
  previous_odometer: number | null;
  miles_driven: number | null;
  mpg: number | null;
  cost_per_mile: number | null;
}

export interface FillUpUpdate {
  timestamp?: string;
  odometer?: number;
  gallons?: number;
  price_per_gallon?: number | null;
  fuel_total?: number | null;
  station_brand?: string | null;
  station_address?: string | null;
  notes?: string | null;
}

export interface Warnings {
  odometer: string | null;
  mpg: string | null;
  fuel_math: string | null;
  receipt_fields: string[];
}

export interface DuplicateCandidate {
  id: number;
  timestamp: string;
  odometer: number;
  gallons: number;
  fuel_total: number | null;
  station_brand: string | null;
}

export interface OCRProcessResponse {
  odometer_value: number | null;
  odometer_confidence: number;
  odometer_raw_text: string;
  odometer_candidates: number[];

  gallons: number | null;
  price_per_gallon: number | null;
  fuel_total: number | null;
  station_brand: string | null;
  station_address: string | null;
  timestamp: string | null;
  receipt_raw_text: string;

  previous_odometer: number | null;
  miles_driven: number | null;
  mpg: number | null;
  cost_per_mile: number | null;

  warnings: Warnings;
  duplicates: DuplicateCandidate[];
}

export interface DashboardStats {
  last_fillup: FillUp | null;
  month_spend: number;
  month_miles: number;
  month_mpg: number | null;
  lifetime_average_mpg: number | null;
  lifetime_mpg: number | null;
  lifetime_total_miles: number;
  lifetime_total_fuel_cost: number;
  lifetime_average_price: number | null;
}

export interface LifetimeStats {
  most_recent_mpg: number | null;
  average_mpg: number | null;
  lifetime_mpg: number | null;
  average_fuel_price: number | null;
  total_gallons: number;
  total_fuel_cost: number;
  total_miles: number;
  current_month_spend: number;
  current_month_miles: number;
  average_monthly_spend: number | null;
  average_monthly_miles: number | null;
  cost_per_mile: number | null;
}

export interface ChartPoint {
  label: string;
  value: number;
}

export interface ChartsResponse {
  mpg_over_time: ChartPoint[];
  price_over_time: ChartPoint[];
  monthly_spend: ChartPoint[];
  monthly_miles: ChartPoint[];
}

export interface ImportRow {
  row_number: number;
  odometer: number | null;
  timestamp: string | null;
  gallons: number | null;
  price_per_gallon: number | null;
  fuel_total: number | null;
  station_address: string | null;
  station_brand: string | null;
  miles_driven: number | null;
  mpg: number | null;
  cost_per_mile: number | null;
  is_duplicate_in_file: boolean;
  is_valid: boolean;
  errors: string[];
}

export interface ImportPreview {
  total: number;
  valid: number;
  errors: number;
  rows: ImportRow[];
}

export interface AppSettings {
  theme: "light" | "dark" | "system";
  timezone: string;
  ocr_engine: string;
}
